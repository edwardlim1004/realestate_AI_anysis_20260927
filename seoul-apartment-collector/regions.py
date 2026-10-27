"""MOLIT five-digit LAWD_CD coverage for Seoul, Gyeonggi and Daejeon.

Current codes: https://www.naqs.go.kr/f2t/com/searchSgList.do
Hwaseong (2026-02-01): https://www.mois.go.kr/frt/bbs/type001/commonSelectBoardArticle.do?bbsId=BBSMSTR_000000000052&nttId=122595
Bucheon (2024-01-01): https://www.mois.go.kr/frt/bbs/type001/commonSelectBoardArticle.do?bbsId=BBSMSTR_000000000052&nttId=105833
Retired codes remain separate raw API partitions; do not add parent-city codes
to current child districts, which would double-count the same current area.
Boundary months are inclusive on both sides of a mid-month reorganization.
"""

SEOUL = {
    '11110':'종로구', '11140':'중구', '11170':'용산구', '11200':'성동구',
    '11215':'광진구', '11230':'동대문구', '11260':'중랑구', '11290':'성북구',
    '11305':'강북구', '11320':'도봉구', '11350':'노원구', '11380':'은평구',
    '11410':'서대문구', '11440':'마포구', '11470':'양천구', '11500':'강서구',
    '11530':'구로구', '11545':'금천구', '11560':'영등포구', '11590':'동작구',
    '11620':'관악구', '11650':'서초구', '11680':'강남구', '11710':'송파구',
    '11740':'강동구',
}
GYEONGGI = {
    '41111':'수원시 장안구', '41113':'수원시 권선구',
    '41115':'수원시 팔달구', '41117':'수원시 영통구',
    '41131':'성남시 수정구', '41133':'성남시 중원구', '41135':'성남시 분당구',
    '41150':'의정부시', '41171':'안양시 만안구', '41173':'안양시 동안구',
    '41192':'부천시 원미구', '41194':'부천시 소사구', '41196':'부천시 오정구',
    '41210':'광명시', '41220':'평택시', '41250':'동두천시',
    '41271':'안산시 상록구', '41273':'안산시 단원구',
    '41281':'고양시 덕양구', '41285':'고양시 일산동구', '41287':'고양시 일산서구',
    '41290':'과천시', '41310':'구리시', '41360':'남양주시', '41370':'오산시',
    '41390':'시흥시', '41410':'군포시', '41430':'의왕시', '41450':'하남시',
    '41461':'용인시 처인구', '41463':'용인시 기흥구', '41465':'용인시 수지구',
    '41480':'파주시', '41500':'이천시', '41550':'안성시', '41570':'김포시',
    '41591':'화성시 만세구', '41593':'화성시 효행구',
    '41595':'화성시 병점구', '41597':'화성시 동탄구',
    '41610':'광주시', '41630':'양주시', '41650':'포천시', '41670':'여주시',
    '41800':'연천군', '41820':'가평군', '41830':'양평군',
    # Historical LAWD_CD values needed for pre-reorganization contract months.
    '41190':'부천시', '41195':'부천시 원미구(구코드)',
    '41197':'부천시 소사구(구코드)', '41199':'부천시 오정구(구코드)',
    '41590':'화성시', '41730':'여주군',
}
DAEJEON = {
    '30110':'동구', '30140':'중구', '30170':'서구',
    '30200':'유성구', '30230':'대덕구',
}
DISTRICTS = {**SEOUL, **GYEONGGI, **DAEJEON}
LABELS = {'seoul':'서울', 'gyeonggi':'경기도', 'daejeon':'대전'}
PROVINCE_NAMES = {'seoul':'서울특별시', 'gyeonggi':'경기도', 'daejeon':'대전광역시'}
PERIODS = {
    '41192':('202401',None), '41194':('202401',None), '41196':('202401',None),
    '41190':('201607','202312'),
    '41195':(None,'201607'), '41197':(None,'201607'), '41199':(None,'201607'),
    '41590':(None,'202601'),
    '41591':('202602',None), '41593':('202602',None),
    '41595':('202602',None), '41597':('202602',None),
    '41670':('201309',None), '41730':(None,'201309'),
}


def region_for(code):
    if code.startswith('11'): return 'seoul'
    if code.startswith('41'): return 'gyeonggi'
    if code.startswith('30'): return 'daejeon'
    raise ValueError('Unsupported province code')


def in_month(code, ym):
    start, end = PERIODS.get(code, (None,None))
    return code in DISTRICTS and (start is None or ym >= start) and (end is None or ym <= end)


def select(region='all'):
    if region == 'seoul': return list(SEOUL)
    if region == 'gyeonggi': return list(GYEONGGI)
    if region == 'daejeon': return list(DAEJEON)
    if region == 'all': return list(DISTRICTS)
    raise ValueError('Unsupported region')


def full_name(code):
    return PROVINCE_NAMES[region_for(code)] + ' ' + DISTRICTS[code]

