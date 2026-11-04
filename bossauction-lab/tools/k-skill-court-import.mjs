/**
 * Read-only, offline adapter for normalized `court-auction-notice-search search` JSON.
 * No HTTP calls, scraping, credentials, or filesystem writes until the CLI is invoked.
 */
import {readFile, writeFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';

const MAX_ITEMS = 10000;
const REGIONS = [
  '서울특별시','부산광역시','대구광역시','인천광역시','광주광역시',
  '대전광역시','울산광역시','세종특별자치시','경기도','강원특별자치도',
  '강원도','충청북도','충청남도','전북특별자치도','전라북도',
  '전라남도','경상북도','경상남도','제주특별자치도','제주도'
];
const LARGE_TYPES = {'10000':'토지','20000':'건물'};
function trim(value){return typeof value==='string'?value.trim():'';}
function price(value, label) {
  if(value===null||value===undefined||value==='')return null;
  if(typeof value!=='number'||!Number.isSafeInteger(value)||value<0)throw Error(`${label}: 유효하지 않은 원 단위 정수`);
  return value;
}
function validDate(value) {
  if(value===null||value===undefined||value==='')return '';
  if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(value))throw Error('매각기일 형식 오류');
  const d=new Date(value+'T00:00:00Z');
  if(!Number.isFinite(d.getTime())||d.toISOString().slice(0,10)!==value)throw Error('존재하지 않는 매각기일');
  return value;
}
function getRegion(item, address) {
  const rawRegion=trim(item.raw?.hjguSido);
  if(REGIONS.includes(rawRegion))return rawRegion;
  return REGIONS.find(name=>address.startsWith(name))||'지역 미확인';
}
function safeId(value,label){
  const s=trim(value);
  if(!s||s.length>100||!/^[\p{L}\p{N}._:-]+$/u.test(s))throw Error(`${label}: 사건/물건 식별자 오류`);
  return s;
}
function normalizeItem(item,index) {
  if(!item||typeof item!=='object'||Array.isArray(item))throw Error(`${index}번째 물건 형식 오류`);
  const court=safeId(item.courtCode,`${index}번째 법원코드`);
  const caseNumber=safeId(item.displayCaseNumber||item.caseNumber,`${index}번째 사건번호`);
  const itemNumber=safeId(item.itemNumber||item.itemSeq,`${index}번째 물건번호`);
  const location=trim(item.address);
  if(!location)throw Error(`${index}번째 물건 주소 누락`);
  const region=getRegion(item,location);
  const type=LARGE_TYPES[trim(item.usageCodes?.large)]||'용도 미확인';
  const failures=item.flbdCount;
  if(!Number.isInteger(failures)||failures<0||failures>100)throw Error(`${index}번째 유찰횟수 누락/오류`);
  // Raw WGS84 fields may have rounded or unverified precision. Never turn them into map pins.
  return {
    id:`court:${court}:${caseNumber}:${itemNumber}`,
    channel:'court',
    title:`${caseNumber} 물건 ${itemNumber} · ${type}`,
    region, type, location,
    authority:trim(item.courtName)||court,
    appraisal:price(item.appraisedPrice,`${index}번째 감정평가액`),
    minimum:price(item.minimumSalePrice,`${index}번째 최저매각가격`),
    date:validDate(item.saleDate),
    failures,
    area:null,
    lat:null, lng:null, coordinateSource:null, sourceUrl:null
  };
}
export function convertKSkillCourtSearch(payload,{now=new Date()}={}) {
  if(!payload||typeof payload!=='object'||Array.isArray(payload))throw Error('JSON 객체가 필요합니다.');
  if(payload.status||payload.data?.dlt_srchResult)throw Error('원본 WebSquare 응답은 지원하지 않습니다. k-skill의 정규화된 search 결과 JSON을 사용하세요.');
  if(!Array.isArray(payload.items)||!payload.page||typeof payload.page!=='object')throw Error('court-auction-notice-search search 결과(items/page)가 아닙니다. 매각공고 목록·사건조회 결과는 지원하지 않습니다.');
  if(payload.items.length<1||payload.items.length>MAX_ITEMS)throw Error(`결과는 1~${MAX_ITEMS}건이어야 합니다.`);
  if(!(now instanceof Date)||!Number.isFinite(now.getTime()))throw Error('변환 시각 오류');
  const lots=payload.items.map((x,i)=>normalizeItem(x,i+1));
  const seen=new Set();for(const lot of lots){if(seen.has(lot.id))throw Error(`중복 물건 ID: ${lot.id}`);seen.add(lot.id);}
  return {
    sourceName:'k-skill 법원경매 검색 결과 (공고 원문 재확인 필요)',
    // Conversion time is not an official auction publication timestamp.
    collectedAt:now.toISOString(),
    lots,
    integration:{source:'NomaDamas/k-skill / court-auction-notice-search',mode:'offline-manual-import',verified:false,conversionTimestampOnly:true,page:payload.page.pageNo??null,upstreamTotal:payload.page.totalCount??null,coordinatesVerified:false}
  };
}
async function main(args){
  if(args.length<1||args.length>2||args.includes('--help')){
    throw Error('사용법: node tools/k-skill-court-import.mjs <정규화된-search-결과.json> [변환-결과.json]');
  }
  const input=JSON.parse(await readFile(args[0],'utf8'));
  const converted=convertKSkillCourtSearch(input);
  const output=JSON.stringify(converted,null,2)+'\n';
  if(args[1]){await writeFile(args[1],output,{flag:'wx'});console.error(`변환 완료: ${converted.lots.length}건 → ${args[1]}`);}
  else process.stdout.write(output);
}
if(process.argv[1]&&import.meta.url===pathToFileURL(resolve(process.argv[1])).href){
  main(process.argv.slice(2)).catch(e=>{console.error(`k-skill 변환 실패: ${e.message}`);process.exitCode=1;});
}
