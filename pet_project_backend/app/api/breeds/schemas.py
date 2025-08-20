# app/api/breeds/schemas.py
from marshmallow import Schema, fields, validate, post_load
from typing import Optional

class BreedSchema(Schema):
    """
    개별 품종 정보를 위한 스키마
    """
    breed_name = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    life_expectancy = fields.Float(required=True, validate=validate.Range(min=0, max=30))
    height_cm = fields.Nested('HeightWeightSchema', required=True)
    weight_kg = fields.Nested('HeightWeightSchema', required=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

class HeightWeightSchema(Schema):
    """
    키/몸무게 정보 (성별별)를 위한 스키마
    """
    male = fields.Float(required=True, validate=validate.Range(min=0), allow_none=True)
    female = fields.Float(required=True, validate=validate.Range(min=0), allow_none=True)

class BreedListSchema(Schema):
    """
    품종 목록 조회 응답을 위한 스키마
    """
    breeds = fields.List(fields.Nested(BreedSchema), required=True)
    total_count = fields.Int(required=True, validate=validate.Range(min=0))

class BreedSummarySchema(Schema):
    """
    품종 요약 정보를 위한 스키마 (드롭다운 등에서 사용)
    """
    breed_name = fields.Str(required=True)
    life_expectancy = fields.Float(required=True)

class BreedSummaryListSchema(Schema):
    """
    품종 요약 목록 조회 응답을 위한 스키마
    """
    breeds = fields.List(fields.Nested(BreedSummarySchema), required=True)
    total_count = fields.Int(required=True, validate=validate.Range(min=0))

class BreedSearchSchema(Schema):
    """
    품종 검색 요청을 위한 스키마
    """
    query = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    limit = fields.Int(missing=50, validate=validate.Range(min=1, max=100))
    offset = fields.Int(missing=0, validate=validate.Range(min=0))

class ErrorResponseSchema(Schema):
    """
    에러 응답을 위한 스키마
    """
    error_code = fields.Str(required=True)
    message = fields.Str(required=True)
    details = fields.Raw(required=False)
