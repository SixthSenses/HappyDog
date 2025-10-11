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
    created_at = fields.DateTime(dump_only=True, format="iso8601")
    updated_at = fields.DateTime(dump_only=True, format="iso8601")

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

class BreedSummaryListSchema(Schema):
    """
    품종 요약 목록 조회 응답을 위한 스키마
    """
    breeds = fields.List(fields.Nested(BreedSummarySchema), required=True)
    total_count = fields.Int(required=True, validate=validate.Range(min=0))


class BreedBasicInfoSchema(Schema):
    """백과사전: 기본 정보"""
    weight = fields.Str(required=False)
    height = fields.Str(required=False)
    life_span = fields.Str(required=False)
    origin = fields.Str(required=False)


class BreedPersonalitySchema(Schema):
    """백과사전: 성격/특징"""
    strengths = fields.Str(required=False)
    weaknesses = fields.Str(required=False)
    traits = fields.Str(required=False)


class BreedGuideSchema(Schema):
    """품종 백과사전 콘텐츠 스키마"""
    breed_name = fields.Str(required=True)
    english_name = fields.Str(required=False)
    basic_info = fields.Nested(BreedBasicInfoSchema, required=False)
    personality = fields.Nested(BreedPersonalitySchema, required=False)
    common_diseases = fields.List(fields.Str(), required=False)
    care_points = fields.List(fields.Str(), required=False)

class BreedSearchSchema(Schema):
    """
    품종 검색 요청을 위한 스키마
    """
    query = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    limit = fields.Int(load_default=50, validate=validate.Range(min=1, max=100))
    offset = fields.Int(load_default=0, validate=validate.Range(min=0))

class ErrorResponseSchema(Schema):
    """
    에러 응답을 위한 스키마
    """
    error_code = fields.Str(required=True)
    message = fields.Str(required=True)
    details = fields.Raw(required=False)


class BreedExistsResponseSchema(Schema):
    """품종 존재 여부 확인 응답."""
    breed_name = fields.Str(required=True)
    exists = fields.Boolean(required=True)
