# goodprice.go.kr (행정안전부 착한가격업소) 사이트 분석

조사일: 2026-09-19 / 방법: 브라우저 메뉴 DOM(`ul.gnb`) 원문 + 네트워크(AJAX) 분석 + 샘플 1건 응답 확인

---

## 1. 전체 메뉴 트리 (GNB DOM 원문 그대로)

- 착한가격업소 안내 (/intro/custInfo.do)
  - 소비자편 (/intro/custInfo.do)
  - 업소편 (/intro/bsshInfo.do?tabId=1)
    - 착한가격업소 안내 (/intro/bsshInfo.do?tabId=1)
    - 지정현황 (/intro/bsshInfo.do?tabId=2)
    - 지정기준 (/intro/bsshInfo.do?tabId=3)
    - 지정절차 (/intro/bsshInfo.do?tabId=4)
    - 업소혜택 (/intro/bsshInfo.do?tabId=5)
  - 담당부서 연락처 (/intro/bsshInfo.do?tabId=6)
- 착한가격업소 찾기 (/bssh/bsshList.do)
  - 착한가격업소 찾기 (/bssh/bsshList.do)
- 커뮤니티 (/cmnt/boardList.do?bbsId=BBSCTT_00101)
  - 공지사항 (/cmnt/boardList.do?bbsId=BBSCTT_00101)
  - 카드뉴스 (/cmnt/cardNewsList.do)
  - 홍보자료 (/cmnt/boardList.do?bbsId=BBSCTT_00102)
  - 이용후기 (/cmnt/reviewList.do)
- 업소정보 오류 신고 (/recent/insertBsshInfo.do)
  - 업소정보 오류 신고 (/recent/insertBsshInfo.do)
- 착한가격업소 추천 (/recomm/recommend.do)
  - 착한가격업소 추천 (/recomm/recommend.do)

푸터 링크
- 개인정보처리방침 (/intro/goPersonalInfo.do)
- 서비스 소개 (/intro/bsshInfo.do)
- 유관기관 바로가기: 행정안전부 / 농림축산식품부 / 식품의약품안전처
- 착한가격업소 담당부서 연락처 바로가기: 서울특별시 / 부산광역시 / 대구광역시 / 인천광역시 / 대전광역시 / 울산광역시 / 세종특별자치시 / 경기도 / 강원특별자치도 / 충청북도 / 전남광주통합특별시 / 충청남도 / 전북특별자치도 / 경상북도 / 경상남도 / 제주특별자치도

메인 화면 구성
- 팝업 배너: 추석맞이 착한가격업소 이용후기 이벤트 / 9월 착한가격업소 카드사 할인 행사
- 착한가격업소 찾기(지도, "업소명 또는 메뉴명으로 검색", "지도를 확대하면 업소 목록이 표시됩니다")
- 주요공지(슬라이드) / 카드뉴스(슬라이드, 더보기)
- 알림소식: 공지사항 / 홍보자료 / 보도자료 탭
- 방문후기(슬라이드, 더보기)

## 2. 메뉴별 내용

### 착한가격업소 안내
| 메뉴 | 내용 |
|---|---|
| 소비자편 | 착한가격업소란?(정부·지자체 선정 우수업소), 표찰·스티커 안내, 2011년 제도 시작, 이용 권장 |
| 업소편 > 착한가격업소 안내 | 정의(정부·지자체가 지정·관리하는 물가안정 모범업소), 소비자 측면(저렴한 가격, 우수한 서비스), 업소 측면(다양한 혜택지원, 물가안정, 서민경제 활성화), 4대 가치(저렴한 가격·안전한 재료·친절한 서비스·청결한 가게), 혜택(쓰레기봉투·상하수도 요금 감면 등, 온라인/모바일 홍보) |
| 업소편 > 지정현황 | 2011년 2,497개 → 2026-09-19 기준 12,900개(외식업·이미용업·세탁업 등), 시도별·업종별(외식업/기타 개인서비스업) 차트(2026년 기준) |
| 업소편 > 지정기준 | 가격기준(인근 상권 평균가격 미만 품목, 재지정 시 유지기간 차등 점수) / 공공성 기준(지역화폐 가맹점, 지역특화자원 활용도, 지역사회 공헌도, 메뉴 표시·표찰 부착) / 위생·청결 기준(주방, 매장, 화장실) |
| 업소편 > 지정절차 | 신청(영업자 직접/국민 추천) → 현지실사(민간·공무원 공동) → 심사·검토 → 결정통보 및 지정증 교부 → 지정공고(시장·군수·구청장). 재심사: 신규 1년 후, 사업자 변경 시 1개월 이내. 지정취소: 자진취소·휴폐업·행정처분 |
| 업소편 > 업소혜택 | 행안부·지자체 홍보, 업소별 연 85만원 상당 물품·지방공공요금 지원, 지도검색 서비스 제공 |
| 담당부서 연락처 | 시도/시군구 선택 검색, 표(번호/시도/시군구/담당부서/연락처), 1번 = 행정안전부 본청 지역경제과 044-205-3913 |

### 착한가격업소 찾기 (/bssh/bsshList.do)
- 검색조건
  - 시도: 전체 / 서울특별시 / 부산광역시 / 대구광역시 / 인천광역시 / 대전광역시 / 울산광역시 / 세종특별자치시 / 경기도 / 강원특별자치도 / 충청북도 / 전남광주통합특별시 / 충청남도 / 전북특별자치도 / 경상북도 / 경상남도 / 제주특별자치도
  - 시군구: 시도 선택 연동
  - 업소명 / 대표메뉴 (텍스트)
  - 업종: 전체 / 한식 / 일식 / 양식 / 중식 / 베이커리 / 기타요식업 / 세탁업 / 목욕업 / 숙박업 / 이용업 / 미용업 / 기타비요식업
  - 편의시설: 전체 / 주차 / 포장 / 배달 / 예약 / 남/여 화장실 구분 / 단체이용 가능 / 무선인터넷 / 반려동물 동반 / 유아시설 / 장애인 편의시설 / 임산부 우대 / 지역화폐
  - 버튼: 검색 / 초기화 / 엑셀 다운로드
- 결과: "전체 : 12,900 건", 카드(업소명, 상세보기, 주소, 전화번호, 주요품목, 가격), 페이지네이션
- 지도: 카카오맵 JS SDK(services, clusterer, drawing), 확대 수준에 따라 클러스터 ↔ 개별 마커
- 상세: PC는 팝업(AJAX), 모바일은 페이지 이동

### 커뮤니티
| 메뉴 | 내용 |
|---|---|
| 공지사항 | 30건, 검색(전체/제목/내용), 번호·제목·작성자·작성일·조회수. 이벤트·카드사 할인·소비자 보호센터 등 |
| 카드뉴스 | 3건: 착한가격업소, 알뜰한 소비의 시작!(2026-05-21) / 착한가격업소 방문인증 챌린지(2025-11-25) / 착한가격업소 제도 소개(2025-11-24) |
| 홍보자료 | 0건 |
| 이용후기 | 1,538건, 작성자 마스킹(이**), 글쓰기 가능, 게시물 삭제 기준 안내 |

### 업소정보 오류 신고
- 개인정보수집동의 후 신고. 대상: 상호 변경·폐업 / 주소·연락처·영업시간 등 상이 / 가격 상이

### 착한가격업소 추천
- 개인정보수집동의 후 추천 입력

## 3. 데이터 구조 (지도·상세 AJAX)

### 3.1 엔드포인트
| 용도 | 방식 | URL | 파라미터 |
|---|---|---|---|
| 지도 데이터 | POST | /bssh/selectMapData.json | swLat, swLng, neLat, neLng, level + 검색조건(srchCtpvCd, srchSggCd, srchIndutyCdArr, srchParkingYn 등) |
| 상세(PC) | POST | /bssh/bsshInfo.json | bsshSn |
| 상세(페이지) | GET 가능 | /bssh/bsshInfo.do?bsshSn=955 | bsshSn |
| 엑셀 | POST | /bssh/bsshPageExcel.do | 검색조건 (내용 미확인) |
| 공통코드 | POST | /comm/sys/selectCommCodeList.json | — |

※ 모두 사이트 내부용 AJAX이며 공식 공개 API는 아님

### 3.2 응답 필드 (샘플: bsshSn=955 인사동칼국수)
| 필드 | 의미 | 샘플 |
|---|---|---|
| bsshSn | **업소 고유번호** | 955 |
| bsshNm | 업소명 | 인사동칼국수 |
| **lat / lot** | **위도 / 경도** | 37.5720973140597 / 126.985392406484 |
| indutyCd / indutyNm | 업종코드/명 | 12 / 한식 (지도 응답에선 "한식_면류") |
| ctpvCd / ctpvNm, sggCd / sggNm | 시도·시군구 코드/명 | 11 서울특별시 / 11110 종로구 |
| roadNmAddr / roadNmDtlAddr / roadNmCd | 도로명주소 / 상세 / 도로명코드 | 인사동5길 25 / 1층 / 03162 |
| bsshTelno | 전화 | 02-737-1151 |
| bsnHr | **영업시간** | 월~금 07:00-19:00, 토 10:00~15:00, 일·공휴일 휴무 |
| menuList[] (menuNm, menuPc, menuDsgnYn) | 메뉴·가격·착한가격 지정메뉴 여부 | 칼국수 7,500 / 된장찌개 7,500 / 순두부 7,500 |
| parkingYn, packingYn, dlvrYn, rsvtYn, mwmnToiletSeYn, grpUsePosblYn, wrlessIntnetPvsnYn, componAnimalAcmpnyYn, infntFcltyYn, pwdbsFcltyYn, pregnantPrefrYn, areaCrrncy*Yn | **편의시설 12종 + 지역화폐** | 전부 N |
| fileList[] | **업소 사진** | /bssh/20240730/...png (썸네일 /thumb) |
| deptTelNo[] | 담당 부서·연락처 | 종로구청 일자리정책과 02-2148-2322 |
| dsgnYn, dsgnYmd, dsgnRtrcnYmd, dsgnRtrcnResn | 지정여부·지정일·취소일·취소사유 | Y (나머지 비공개/빈값) |
| brno, bsmnNm | 사업자번호·대표자 | 비공개(빈값) |

### 3.3 공공데이터포털 CSV와 비교
| 항목 | data.go.kr CSV | goodprice.go.kr 내부 데이터 |
|---|---|---|
| 건수 | 12,645 (분기) | 12,900 (실시간) |
| 고유ID | 없음 | bsshSn |
| 좌표 | 없음 | lat/lot |
| 시도/시군구 코드 | 명칭만 | 코드+명칭 |
| 메뉴 | 4개 고정 컬럼 | 목록(개수 가변) + 지정메뉴 여부 |
| 영업시간 | 없음 | 있음 |
| 편의시설 | 없음 | 12종 Y/N |
| 사진 | 없음 | 있음 |
| 담당부서 | 없음 | 있음 |

## 4. robots.txt (원문)
```
User-agent: *
Disallow: /cmnt/reviewList.do
Disallow: /cmnt/reviewListDetail.do
Allow: /$
Allow: /sitemap.xml

User-agent: Googlebot
User-agent: Daumoa
User-agent: Yeti
User-agent: NaverBot
Disallow: /
Allow: /$
Allow: /sitemap.xml

Sitemap: https://www.goodprice.go.kr/sitemap.xml
```
- 이용후기 게시판은 수집 금지 명시
- 주요 검색엔진 봇은 메인 외 전체 차단
- sitemap.xml은 실제로는 관리자 로그인 화면 HTML을 반환(사이트맵 미운영)
- 개인정보처리방침 페이지 본문 비어 있음 → 데이터 이용 약관 별도 명시 없음
