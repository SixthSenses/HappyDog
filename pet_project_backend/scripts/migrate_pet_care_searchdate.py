#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
펫케어 기록 searchDate 마이그레이션 스크립트

목적: 기존 펫케어 기록의 searchDate를 UTC 기준에서 KST 기준으로 재계산

배경:
- 기존 코드는 UTC 기준으로 searchDate를 생성했음
- 이로 인해 KST 00:00~08:59 사이 기록들의 searchDate가 하루 전으로 저장됨
- 예: 2025-10-10 00:48 (KST) 기록 → searchDate "2025-10-09" (잘못됨)

실행 조건:
- 2025년 10월 1일 이후 데이터만 마이그레이션 (최근 데이터만)
- 프로덕션 환경에서는 백업 후 실행 권장

사용법:
    python pet_project_backend/scripts/migrate_pet_care_searchdate.py [--dry-run] [--start-date YYYY-MM-DD]
"""

import os
import sys
import logging
import argparse
from datetime import datetime, timezone
from typing import Dict, Any

# 프로젝트 루트를 Python path에 추가
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)

from google.cloud import firestore
from app.utils.datetime_utils import DateTimeUtils

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SearchDateMigrator:
    """펫케어 기록 searchDate 마이그레이션 클래스"""
    
    def __init__(self, db_client: firestore.Client, dry_run: bool = False):
        self.db = db_client
        self.logs_ref = db_client.collection('pet_care_logs')
        self.dry_run = dry_run
        
    def migrate_records(self, start_date: str = '2025-10-01') -> Dict[str, int]:
        """
        searchDate를 KST 기준으로 재계산하여 업데이트
        
        Args:
            start_date: 마이그레이션 시작 날짜 (YYYY-MM-DD)
            
        Returns:
            통계 정보 (total, updated, skipped, errors)
        """
        stats = {
            'total': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0
        }
        
        logger.info(f"{'[DRY RUN] ' if self.dry_run else ''}마이그레이션 시작: start_date={start_date}")
        
        # 특정 날짜 이후의 기록만 조회
        query = self.logs_ref.where('searchDate', '>=', start_date)
        
        batch = self.db.batch()
        batch_count = 0
        
        try:
            for doc in query.stream():
                stats['total'] += 1
                data = doc.to_dict()
                
                try:
                    result = self._process_record(doc.id, data, batch)
                    
                    if result == 'updated':
                        stats['updated'] += 1
                        batch_count += 1
                    elif result == 'skipped':
                        stats['skipped'] += 1
                    
                    # Firestore batch limit: 500
                    if batch_count >= 500:
                        if not self.dry_run:
                            batch.commit()
                            logger.info(f"배치 커밋 완료: {batch_count}개 레코드")
                        batch = self.db.batch()
                        batch_count = 0
                        
                except Exception as e:
                    stats['errors'] += 1
                    logger.error(f"레코드 처리 오류 {doc.id}: {e}")
                    continue
            
            # 남은 배치 커밋
            if batch_count > 0 and not self.dry_run:
                batch.commit()
                logger.info(f"최종 배치 커밋 완료: {batch_count}개 레코드")
                
        except Exception as e:
            logger.error(f"마이그레이션 중 오류 발생: {e}", exc_info=True)
            raise
        
        # 결과 요약
        logger.info("=" * 60)
        logger.info(f"{'[DRY RUN] ' if self.dry_run else ''}마이그레이션 완료")
        logger.info(f"  총 레코드: {stats['total']}")
        logger.info(f"  업데이트됨: {stats['updated']}")
        logger.info(f"  스킵됨: {stats['skipped']}")
        logger.info(f"  오류: {stats['errors']}")
        logger.info("=" * 60)
        
        return stats
    
    def _process_record(self, doc_id: str, data: Dict[str, Any], batch) -> str:
        """
        개별 레코드 처리
        
        Returns:
            'updated': 업데이트됨
            'skipped': 스킵됨 (변경 불필요)
        """
        timestamp = data.get('timestamp')
        current_search_date = data.get('searchDate')
        
        if not timestamp:
            logger.warning(f"레코드 {doc_id}: timestamp 없음, 스킵")
            return 'skipped'
        
        # Firestore Timestamp를 datetime으로 변환
        if hasattr(timestamp, 'tzinfo'):
            ts_dt = timestamp
        else:
            # timestamp가 이미 datetime인 경우
            ts_dt = timestamp
        
        # timezone-aware로 변환
        if ts_dt.tzinfo is None:
            ts_dt = ts_dt.replace(tzinfo=timezone.utc)
        
        # KST 기준으로 searchDate 재계산
        new_search_date = DateTimeUtils.to_kst_date_str(ts_dt)
        
        if new_search_date != current_search_date:
            log_msg = f"레코드 {doc_id}: {current_search_date} -> {new_search_date}"
            
            if self.dry_run:
                logger.info(f"[DRY RUN] {log_msg}")
            else:
                logger.info(log_msg)
                doc_ref = self.logs_ref.document(doc_id)
                batch.update(doc_ref, {'searchDate': new_search_date})
            
            return 'updated'
        else:
            logger.debug(f"레코드 {doc_id}: 변경 불필요 (searchDate={current_search_date})")
            return 'skipped'


def main():
    """메인 실행 함수"""
    parser = argparse.ArgumentParser(
        description='펫케어 기록 searchDate를 KST 기준으로 마이그레이션'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='실제 업데이트 없이 시뮬레이션만 수행'
    )
    parser.add_argument(
        '--start-date',
        type=str,
        default='2025-10-01',
        help='마이그레이션 시작 날짜 (YYYY-MM-DD, 기본값: 2025-10-01)'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='상세 로그 출력'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Firebase 클라이언트 초기화
    try:
        # 환경변수에서 credential 경로 읽기
        cred_path = os.environ.get('FIREBASE_CREDENTIALS_PATH')
        if cred_path:
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = cred_path
            logger.info(f"Firebase credentials: {cred_path}")
        
        db_client = firestore.Client()
        logger.info("Firestore 클라이언트 초기화 성공")
        
    except Exception as e:
        logger.error(f"Firestore 클라이언트 초기화 실패: {e}")
        logger.error("FIREBASE_CREDENTIALS_PATH 환경변수를 확인하세요")
        return 1
    
    # 마이그레이션 실행
    try:
        migrator = SearchDateMigrator(db_client, dry_run=args.dry_run)
        stats = migrator.migrate_records(start_date=args.start_date)
        
        # 에러가 있으면 종료 코드 1
        return 1 if stats['errors'] > 0 else 0
        
    except Exception as e:
        logger.error(f"마이그레이션 실패: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
