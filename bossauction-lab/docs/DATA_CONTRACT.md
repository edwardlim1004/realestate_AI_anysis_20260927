# 경·공매 데이터 계약 초안

## 엔티티
- AuctionLot: id, source, sourceUrl, caseNumber, itemNumber, auctionType (court | public), address, propertyType, appraisedPriceKRW, minimumBidKRW, scheduleAtKST, status, updatedAtKST, provenance.
- AuctionEvent: lotId, eventAtKST, eventType, bidMinimumKRW, observedResult, provenance.
- Document: lotId, documentType, sourceUrl, publishedAt, sha256, accessRight.
- Watchlist: ownerId, lotId, createdAt (서버 운영 시 인증 필요).
- RiskReview: lotId, documentIds, checks[], reviewedBy, reviewedAt. 자동 위험 점수를 확정 법률판단으로 표시 금지.

## 정합성·수집 게이트
1. source + original lot/case/item key로 중복 제거.
2. 원문의 기준일, 입찰기간/매각기일, 타임존을 별도 필드에 보존.
3. 결측값은 null, 절대 0이나 가상의 법원·사건번호로 대체하지 않음.
4. 취소·변경·유찰·매각 결과를 변경이력으로 관리.
5. 페이지에는 최근 검증된 동기화 시점과 데이터 출처를 표시.
6. 허가된 API만 사용하고 robots/약관/호출 제한 준수.

## 데모 변환
지금의 DEMO-001~008은 실제 사건 ID가 아니며 모든 날짜·금액은 인위적으로 작성한 샘플이다.
