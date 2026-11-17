// Etapa 3: gera o PDF do relatório (A4 deitado, todas as abas em sequência).
// Uso: node pdf.js <relatorio.html> <saida.pdf>
const {chromium}=require('playwright');const path=require('path');
(async()=>{const [inp,out]=process.argv.slice(2);
const b=await chromium.launch();const p=await b.newPage({viewport:{width:1200,height:900},colorScheme:'light'});
await p.goto('file://'+path.resolve(inp));await p.waitForTimeout(1500);
await p.addStyleTag({content:`.card,.kpirow,.section-title-row,tr,.notecard{break-inside:avoid} .section-title-row{break-after:avoid} .wrap{padding-block:0!important} table{min-width:0!important;font-size:11px} tbody td,thead th{padding:5px 6px} td .mini a{max-width:190px} thead th{position:static} .tablewrap{overflow:visible} #p-tabela,#p-criterios{break-before:page}`});
await p.pdf({path:out,format:'A4',landscape:true,printBackground:true,margin:{top:'12mm',bottom:'12mm',left:'10mm',right:'10mm'},scale:0.8});
await b.close();})();
