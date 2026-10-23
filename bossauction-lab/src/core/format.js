export function won(value){if(!Number.isFinite(value))return "-";const abs=Math.abs(value);const sign=value<0?"−":"";if(abs>=100000000)return sign+(abs/100000000).toLocaleString("ko-KR",{maximumFractionDigits:2})+"억 원";return sign+(abs/10000).toLocaleString("ko-KR",{maximumFractionDigits:0})+"만 원";}
export function percent(value){return Number.isFinite(value)?value.toFixed(1)+"%":"-";}
export function discount(lot){return (1-lot.minimum/lot.appraisal)*100;}
export function dateKR(date){const parts=date.split("-");return parts[0]+"."+parts[1]+"."+parts[2]+".";}
export function escapeHTML(text){return String(text).replace(/[&<>"']/g,(c)=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
export function moneyInput(value){return Math.round(value/10000);}