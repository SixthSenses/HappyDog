#!/usr/bin/env python
"""
Unified OpenAPI spec builder (lightweight path).

Features:
    - Introspects Flask app routes (excludes static)
    - Parses docstring first line as summary, rest as description
    - Injects standardized error responses from error_catalog
    - Optional docs-mode to skip heavy external init (Firebase, ML, OpenAI)
    - Optional YAML output
    - Optional validation via prance
    - NEW: Pretty output file alongside main output (JSON)
    - NEW: Basic path parameter extraction (<param>) -> parameters list
    - NEW: Optional server list & tag injection
    - NEW: Stats summary (#paths / #operations / #tags) printed
    - NEW: Compressed JSON (no indentation) option when --minify supplied

Usage Examples:
    python pet_project_backend/scripts/swagger_build.py \
            --app pet_project_backend.app:create_app --out openapi.json --validate --docs-mode

    python pet_project_backend/scripts/swagger_build.py \
            --app pet_project_backend.app:create_app --out openapi.json --pretty-out openapi_pretty.json

Notes:
    - For rich example-based schemas previously produced by generate_swagger.py, a future
        enhancement could merge decorator metadata. This unified builder provides a stable,
        minimal contract for CI drift detection while remaining extensible.
"""
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path as _Path

# Ensure pet_project_backend and repository root on sys.path regardless of CWD
_scripts_dir = _Path(__file__).resolve().parent          # .../pet_project_backend/scripts
_backend_root = _scripts_dir.parent                      # .../pet_project_backend
_repo_root = _backend_root.parent                        # repo root containing pet_project_backend
for _p in [str(_backend_root), str(_repo_root)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
import importlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple, Pattern, Optional, Set, Type
from collections import defaultdict

# Ensure project root & pet_project_backend root on sys.path when executed from repo root
# SCRIPT_DIR = Path(__file__).resolve().parent
# PROJECT_ROOT = SCRIPT_DIR.parent.parent  # pet_project_backend/
# REPO_ROOT = PROJECT_ROOT.parent
# for p in [str(PROJECT_ROOT), str(REPO_ROOT)]:
#     if p not in sys.path:
#         sys.path.insert(0, p)

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # optional

# Lazy prance import
try:
    from prance import BaseParser  # type: ignore
except Exception:  # pragma: no cover
    BaseParser = None  # type: ignore

# --- Helpers -----------------------------------------------------------------

def load_app(app_path: str):
    """Load Flask app from string like 'app:create_app' or 'module:app'."""
    if ':' not in app_path:
        raise ValueError("--app must be in form 'module:attr_or_factory'")
    module_name, attr = app_path.split(':', 1)
    module = importlib.import_module(module_name)
    obj = getattr(module, attr)
    if callable(obj):
        return obj()
    return obj

DOC_RE = re.compile(r"^(?P<summary>[^\n]+)(?:\n\n?(?P<desc>[\s\S]+))?", re.MULTILINE)


def parse_doc(doc: str | None) -> Tuple[str, str]:
    if not doc:
        return "", ""
    m = DOC_RE.search(doc.strip())
    if not m:
        return doc.strip(), ""
    return m.group('summary').strip(), (m.group('desc') or '').strip()


# Import error catalog
def build_error_responses() -> Dict[str, Any]:
    """Build reusable error response component refs.

    All error responses now share the canonical ErrorResponseSchema.
    Individual response objects retain description from catalog for human context.
    """
    try:
        from pet_project_backend.app.utils.error_catalog import ERRORS  # noqa: E402
    except Exception as e:  # pragma: no cover
        print(f"[warn] error_catalog import 실패: {e}", file=sys.stderr)
        return {}
    responses: Dict[str, Any] = {}
    for code, spec in ERRORS.items():
        responses[code] = {
            'description': spec.message,
            'content': {
                'application/json': {
                    'schema': {'$ref': '#/components/schemas/ErrorResponseSchema'}
                }
            }
        }
    return responses


def _extract_path_parameters(rule_str: str) -> List[Dict[str, Any]]:
    """Extract path parameters from a Flask rule string.

    Supports patterns:
        <name>
        <converter:name>

    Converter -> OpenAPI type mapping applied when recognized.
    Unknown converters default to string.
    """
    params: List[Dict[str, Any]] = []
    pattern = r"<(?:(?P<conv>[^:<>]+):)?(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)>"
    type_map = {
        'string': ('string', None),
        'path': ('string', None),  # Flask path captures slashes
        'int': ('integer', 'int32'),
        'float': ('number', 'float'),
        'uuid': ('string', 'uuid'),
        'any': ('string', None),  # any from Werkzeug
    }
    for match in re.finditer(pattern, rule_str):
        conv = match.group('conv') or 'string'
        name = match.group('name')
        oapi_type, oapi_format = type_map.get(conv, ('string', None))
        schema: Dict[str, Any] = {'type': oapi_type}
        if oapi_format:
            schema['format'] = oapi_format
        params.append({
            'name': name,
            'in': 'path',
            'required': True,
            'schema': schema,
            'description': f"Path parameter '{name}' (converter: {conv})"
        })
    return params


DOC_TAG_REQUEST_RE = re.compile(r'^\s*RequestSchema:\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)$', re.MULTILINE)
DOC_TAG_RESPONSE_RE = re.compile(r'^\s*ResponseSchema(?:\[(?P<code>\d{3})\])?:\s*(?P<name>[A-Za-z_][A-Za-z0-9_]*)$', re.MULTILINE)


def extract_doc_tags(raw_doc: str | None) -> Tuple[Optional[str], Dict[str, str]]:
    """Extract Request/Response schema tags from full docstring body.

    Returns: (request_schema_name_or_None, {status_code: schema_name})
    Default status code for ResponseSchema without explicit code is '200'.
    """
    if not raw_doc:
        return None, {}
    req_match = DOC_TAG_REQUEST_RE.search(raw_doc)
    request_schema = req_match.group('name') if req_match else None
    responses: Dict[str, str] = {}
    for m in DOC_TAG_RESPONSE_RE.finditer(raw_doc):
        code = m.group('code') or '200'
        responses[code] = m.group('name')
    return request_schema, responses


def collect_marshmallow_schemas() -> Dict[str, Any]:
    """Collect marshmallow Schema subclasses from domain schemas.py files.

    Produces a raw intermediate representation: {SchemaName: SchemaClass}.
    Conversion to OpenAPI dict performed later to allow forward ref resolution.
    """
    from marshmallow import Schema  # type: ignore
    schemas: Dict[str, Type[Schema]] = {}
    api_dir = _backend_root / 'app' / 'api'
    if not api_dir.exists():  # pragma: no cover
        return {}
    for domain in api_dir.iterdir():
        if not domain.is_dir():
            continue
        schema_file = domain / 'schemas.py'
        if not schema_file.exists():
            continue
        mod_name = f"pet_project_backend.app.api.{domain.name}.schemas"
        try:
            mod = importlib.import_module(mod_name)
        except Exception as e:  # pragma: no cover
            print(f"[warn][schema] import 실패: {mod_name}: {e}", file=sys.stderr)
            continue
        for attr in dir(mod):
            obj = getattr(mod, attr)
            if isinstance(obj, type):
                try:
                    from marshmallow import Schema as _S  # local alias
                except Exception:  # pragma: no cover
                    continue
                if issubclass(obj, _S) and obj is not _S:
                    # Skip internal / explicit error schema naming pattern optional here
                    if attr.startswith('_'):
                        continue
                    schemas[attr] = obj
    return schemas


def _field_to_oas(field) -> Dict[str, Any]:  # type: ignore
    from marshmallow import fields, validate  # type: ignore
    cls_name = getattr(field, '__class__', type(field)).__name__
    # Class-name based overrides (defensive against subclassing surprises)
    if cls_name == 'Date':
        node: Dict[str, Any] = {'type': 'string', 'format': 'date'}
    elif cls_name == 'Time':
        node = {'type': 'string', 'format': 'time'}
    else:
    # Specific subclasses must be checked BEFORE their base classes
        if isinstance(field, getattr(fields, 'URL', tuple())):
            node = {'type': 'string', 'format': 'uri'}
        elif isinstance(field, getattr(fields, 'Email', tuple())):
            node = {'type': 'string', 'format': 'email'}
        elif isinstance(field, getattr(fields, 'UUID', tuple())):
            node = {'type': 'string', 'format': 'uuid'}
        # Basic scalar mapping
        elif isinstance(field, fields.String):
            node = {'type': 'string'}
        elif isinstance(field, fields.Integer):
            node = {'type': 'integer', 'format': 'int32'}
        elif isinstance(field, fields.Float):
            node = {'type': 'number', 'format': 'float'}
        elif isinstance(field, fields.Boolean):
            node = {'type': 'boolean'}
        elif isinstance(field, getattr(fields, 'Decimal', tuple())):
            node = {'type': 'number'}
        elif isinstance(field, fields.DateTime):
            node = {'type': 'string', 'format': 'date-time'}
        elif isinstance(field, getattr(fields, 'Date', tuple())):
            node = {'type': 'string', 'format': 'date'}
        elif isinstance(field, getattr(fields, 'Time', tuple())):
            node = {'type': 'string', 'format': 'time'}
        elif isinstance(field, fields.List):
            node = {'type': 'array', 'items': _field_to_oas(field.inner)}
        elif isinstance(field, fields.Nested):
            ref_name = field.nested if isinstance(field.nested, str) else field.nested.__name__
            node = {'$ref': f"#/components/schemas/{ref_name}"}
        elif isinstance(field, fields.Dict):
            node = {'type': 'object', 'additionalProperties': {'type': 'string'}}
        else:
            node = {'type': 'object'}

    # Common attributes
    if getattr(field, 'allow_none', False):
        node['nullable'] = True

    # Propagate common validators to OAS
    try:
        validators = list(getattr(field, 'validators', []) or [])
    except Exception:
        validators = []
    for v in validators:
        # Enum support
        if isinstance(v, getattr(validate, 'OneOf', tuple())):
            # v.choices may be a set; convert to sorted list when possible for stability
            try:
                choices = list(v.choices)
            except Exception:
                choices = []
            # Keep string ordering stable if all are strings
            try:
                if all(isinstance(c, str) for c in choices):
                    choices = sorted(choices)
            except Exception:
                pass
            node['enum'] = choices
        # Length constraints
        if isinstance(v, getattr(validate, 'Length', tuple())):
            minv = getattr(v, 'min', None)
            maxv = getattr(v, 'max', None)
            if node.get('type') == 'string':
                if minv is not None:
                    node['minLength'] = minv
                if maxv is not None:
                    node['maxLength'] = maxv
            if node.get('type') == 'array':
                if minv is not None:
                    node['minItems'] = minv
                if maxv is not None:
                    node['maxItems'] = maxv
        # Numeric range
        if isinstance(v, getattr(validate, 'Range', tuple())):
            minv = getattr(v, 'min', None)
            maxv = getattr(v, 'max', None)
            if minv is not None:
                node['minimum'] = minv
            if maxv is not None:
                node['maximum'] = maxv
    return node


def convert_schema_classes(schema_classes: Dict[str, Any]) -> Dict[str, Any]:
    """Convert collected Schema classes into OpenAPI schema objects.
    
    Uses data_key attribute if present to match actual API field names,
    otherwise falls back to the internal field name.
    Extracts class docstring as schema description.
    """
    from marshmallow import Schema  # type: ignore
    result: Dict[str, Any] = {}
    for name, cls in schema_classes.items():
        try:
            inst = cls()  # type: ignore
        except Exception as e:  # pragma: no cover
            print(f"[warn][schema] 인스턴스화 실패 {name}: {e}", file=sys.stderr)
            continue
        required: List[str] = []
        props: Dict[str, Any] = {}
        for fname, field in inst.fields.items():  # type: ignore
            # Use data_key if present (API field name), otherwise use internal field name
            api_field_name = getattr(field, 'data_key', None) or fname
            props[api_field_name] = _field_to_oas(field)
            if getattr(field, 'required', False) and not getattr(field, 'dump_only', False):
                required.append(api_field_name)
        schema_obj: Dict[str, Any] = {'type': 'object', 'properties': props}
        if required:
            schema_obj['required'] = sorted(required)
        
        # Add schema description from class docstring
        doc = getattr(cls, '__doc__', None)
        if doc:
            description = doc.strip()
            if description:
                schema_obj['description'] = description
        
        result[name] = schema_obj
    return result


def build_spec(app, title: str, version: str, *, add_servers: bool = False, add_tags: bool = False, add_security: bool = False, public_path_patterns: List[Pattern[str]] | None = None, strict_doc_tags: bool = False) -> Dict[str, Any]:
    paths: Dict[str, Any] = {}
    tag_map: Dict[str, List[str]] = defaultdict(list)

    doc_tag_warnings: List[str] = []
    collected_schema_classes = collect_marshmallow_schemas()
    collected_schema_names = set(collected_schema_classes.keys())

    for rule in app.url_map.iter_rules():
        if rule.endpoint == 'static':
            continue
        view_func = app.view_functions[rule.endpoint]
        raw_doc = view_func.__doc__ or ''
        summary, desc = parse_doc(raw_doc)
        req_schema_name, resp_schema_map = extract_doc_tags(raw_doc)
        # Basic tag inference: first segment after optional /api
        raw_path = rule.rule
        # Convert Flask style <param> or <type:param> to OpenAPI {param}
        openapi_path = re.sub(r"<(?:(?:[^:<>]+):)?([a-zA-Z_][a-zA-Z0-9_]*)>", r"{\1}", raw_path)
        segs = [s for s in raw_path.lstrip('/').split('/') if s]
        inferred_tag = segs[1] if segs and segs[0] == 'api' and len(segs) > 1 else (segs[0] if segs else 'general')
        operations = {}
        path_params = _extract_path_parameters(raw_path)
        for method in sorted(m for m in rule.methods if m in {'GET', 'POST', 'PUT', 'PATCH', 'DELETE'}):
            op_obj: Dict[str, Any] = {
                'summary': summary or f"{method} {raw_path}",
                'description': desc,
                'responses': {
                    '200': {'description': '성공'},
                    '400': {'$ref': '#/components/responses/VALIDATION_ERROR'},
                    '401': {'$ref': '#/components/responses/UNAUTHORIZED'},
                    '403': {'$ref': '#/components/responses/FORBIDDEN'},
                    '404': {'$ref': '#/components/responses/NOT_FOUND'},
                    '500': {'$ref': '#/components/responses/INTERNAL_ERROR'},
                }
            }
            if path_params:
                op_obj['parameters'] = path_params
            # Inject request body if doc tag present
            if req_schema_name and method in {'POST', 'PUT', 'PATCH'}:
                if req_schema_name not in collected_schema_names:
                    doc_tag_warnings.append(f"missing RequestSchema '{req_schema_name}' for {method} {raw_path}")
                else:
                    op_obj['requestBody'] = {
                        'required': True,
                        'content': {
                            'application/json': {
                                'schema': {'$ref': f"#/components/schemas/{req_schema_name}"}
                            }
                        }
                    }
            elif method in {'POST', 'PUT', 'PATCH'} and strict_doc_tags and not req_schema_name:
                doc_tag_warnings.append(f"missing RequestSchema tag for {method} {raw_path}")

            # Inject response schemas
            if resp_schema_map:
                for status_code, schema_name in resp_schema_map.items():
                    if schema_name not in collected_schema_names:
                        doc_tag_warnings.append(f"missing ResponseSchema '{schema_name}' for {method} {raw_path} status {status_code}")
                        continue
                    op_obj['responses'].setdefault(status_code, {'description': '성공'})
                    op_obj['responses'][status_code]['content'] = {
                        'application/json': {
                            'schema': {'$ref': f"#/components/schemas/{schema_name}"}
                        }
                    }
            elif method == 'GET' and strict_doc_tags and not resp_schema_map:
                doc_tag_warnings.append(f"missing ResponseSchema tag for {method} {raw_path}")
            if add_security:
                # Determine if path is public (skip security) based on regex patterns
                is_public = False
                if public_path_patterns:
                    for pat in public_path_patterns:
                        if pat.search(openapi_path):
                            is_public = True
                            break
                if not is_public:
                    op_obj['security'] = [{'BearerAuth': []}]
            if add_tags:
                op_obj['tags'] = [inferred_tag]
                tag_map[inferred_tag].append(raw_path)
            operations[method.lower()] = op_obj
        path_item = paths.setdefault(openapi_path, {})
        path_item.update(operations)

    # Convert collected schema classes after route scan (ensures all discovered)
    oas_schemas = convert_schema_classes(collected_schema_classes)

    # Ensure canonical ErrorResponseSchema present (if user added to any domain path such as common/schemas.py it will be collected)
    if 'ErrorResponseSchema' not in oas_schemas:
        # Fallback injection (should not normally occur if common/schemas.py exists)
        oas_schemas['ErrorResponseSchema'] = {
            'type': 'object',
            'properties': {
                'error_code': {'type': 'string'},
                'category': {'type': 'string'},
                'retriable': {'type': 'boolean'},
                'message': {'type': 'string'},
                'details': {'type': 'object'}
            },
            'required': ['error_code', 'category', 'retriable']
        }

    spec: Dict[str, Any] = {
        'openapi': '3.0.3',
        'info': {'title': title, 'version': version},
        'paths': paths,
        'components': {
            'schemas': oas_schemas,
            'responses': build_error_responses()
        }
    }
    if add_security:
        spec['components'].setdefault('securitySchemes', {})['BearerAuth'] = {
            'type': 'http',
            'scheme': 'bearer',
            'bearerFormat': 'JWT',
            'description': 'Provide the access token as: Bearer <token>'
        }
    if add_servers:
        spec['servers'] = [
            {'url': 'http://localhost:5000', 'description': 'Development'},
            {'url': 'https://api.happydog.com', 'description': 'Production'}
        ]
    if add_tags and tag_map:
        spec['tags'] = [{'name': t} for t in sorted(tag_map.keys())]
    if doc_tag_warnings:
        prefix = '[strict]' if strict_doc_tags else '[warn]'
        for w in doc_tag_warnings:
            print(f"{prefix} {w}", file=sys.stderr)
        if strict_doc_tags:
            print(f"[fail] strict mode: {len(doc_tag_warnings)} doc tag issues", file=sys.stderr)
            # still return spec for inspection but exit code will be handled in main
            spec['_strict_errors'] = doc_tag_warnings  # type: ignore
    return spec


def validate_spec(spec_dict: Dict[str, Any]):
    if BaseParser is None:
        print("[warn] prance 미설치 - 검증 생략", file=sys.stderr)
        return True
    # Write temp file
    import tempfile
    with tempfile.NamedTemporaryFile('w+', suffix='.json', delete=False, encoding='utf-8') as tmp:
        json.dump(spec_dict, tmp, ensure_ascii=False, indent=2)
        tmp.flush()
        path = tmp.name
    try:
        BaseParser(path)  # will raise if invalid
        print('[ok] OpenAPI validation passed')
        return True
    except Exception as e:  # pragma: no cover
        print(f'[fail] OpenAPI validation failed: {e}', file=sys.stderr)
        return False
    finally:
        try:
            Path(path).unlink()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description='Build OpenAPI spec from Flask app (unified builder)')
    parser.add_argument('--app', required=True, help='Import path to app object or factory (module:attr)')
    parser.add_argument('--out', required=True, help='Output file path (.json or .yaml)')
    parser.add_argument('--title', default='HappyDog API')
    parser.add_argument('--version', default='0.1.0')
    parser.add_argument('--yaml', action='store_true', help='Force YAML output')
    parser.add_argument('--validate', action='store_true', help='Validate with prance if available')
    parser.add_argument('--docs-mode', action='store_true', help='Skip heavy external initializations (Firebase, ML, OpenAI network)')
    parser.add_argument('--pretty-out', help='Optional second file with pretty (indented) JSON output')
    parser.add_argument('--minify', action='store_true', help='Minify JSON output (overrides default indent)')
    parser.add_argument('--add-servers', action='store_true', help='Include server list section')
    parser.add_argument('--add-tags', action='store_true', help='Infer simple tags from first path segment')
    parser.add_argument('--add-security', action='store_true', help='Add BearerAuth security scheme and apply to operations')
    parser.add_argument('--public-path', action='append', default=[], help='Regex pattern for public (unauthenticated) paths; can be repeated')
    parser.add_argument('--strict-doc-tags', action='store_true', help='Fail build if required Request/ResponseSchema tags are missing or unresolved')
    args = parser.parse_args()

    if args.docs_mode:
        os.environ['DOCS_MODE'] = '1'
        print('[info] DOCS_MODE enabled (via --docs-mode)')

    app = load_app(args.app)
    # Compile public path regexes if any
    public_patterns: List[Pattern[str]] = []
    if args.public_path:
        import re as _re
        for p in args.public_path:
            try:
                public_patterns.append(_re.compile(p))
            except Exception as e:  # pragma: no cover
                print(f"[warn] invalid public path regex '{p}': {e}", file=sys.stderr)

    spec = build_spec(
        app,
        args.title,
        args.version,
        add_servers=args.add_servers,
        add_tags=args.add_tags,
        add_security=args.add_security,
        public_path_patterns=public_patterns or None,
        strict_doc_tags=args.strict_doc_tags
    )

    out_path = Path(args.out)
    if args.yaml or out_path.suffix.lower() in {'.yml', '.yaml'}:
        if yaml is None:
            print('PyYAML 미설치 - pip install pyyaml 필요', file=sys.stderr)
            sys.exit(2)
        text = yaml.safe_dump(spec, sort_keys=False, allow_unicode=True)
    else:
        if args.minify:
            text = json.dumps(spec, ensure_ascii=False, separators=(',', ':'))
        else:
            text = json.dumps(spec, ensure_ascii=False, indent=2)

    out_path.write_text(text, encoding='utf-8')
    print(f'[ok] Spec written to {out_path}')

    # Optional pretty secondary file (only for JSON primary output)
    if args.pretty_out and not (args.yaml or out_path.suffix.lower() in {'.yml', '.yaml'}):
        pretty_path = _Path(args.pretty_out)
        pretty_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'[ok] Pretty spec written to {pretty_path}')

    # Stats summary
    path_count = len(spec['paths'])
    op_count = sum(len(m) for m in spec['paths'].values())
    tag_count = len(spec.get('tags', []))
    print(f'[stats] paths={path_count} operations={op_count} tags={tag_count}')

    strict_failed = bool(spec.get('_strict_errors')) if isinstance(spec, dict) else False
    if args.validate:
        if not validate_spec(spec):
            sys.exit(3)
    if strict_failed:
        sys.exit(4)

if __name__ == '__main__':
    main()
