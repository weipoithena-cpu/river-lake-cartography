const fs = require('fs');
const assert = require('node:assert/strict');
const { JSDOM } = require('jsdom');
const base = require('node:path').join(__dirname, '..', 'app', 'web') + require('node:path').sep;
const html = fs.readFileSync(base + 'index.html', 'utf8');
const script = fs.readFileSync(base + 'app.js', 'utf8');
const dom = new JSDOM(html.replace('__APP_TOKEN__', 'test-token'), {url:'http://127.0.0.1:8765/', runScripts:'outside-only'});
const w = dom.window;
const d = w.document;
w.HTMLElement.prototype.scrollIntoView = function(){};
w.HTMLAnchorElement.prototype.click = function(){ downloads.push({name:this.download, href:this.href}); };
w.URL.createObjectURL = () => 'blob:http://127.0.0.1:8765/test-image';
w.URL.revokeObjectURL = () => {};
w.confirm = () => true;
w.open = () => {};
let clipboard = '';
Object.defineProperty(w.navigator, 'clipboard', {value:{writeText:async text=>{clipboard=text;}}});
const calls=[]; const downloads=[];
let taskNumber=0; const tasks={};
function result(failed=false,title='Example Map') {return {
 project_id:'project_1', title, project_path:'C:\\Maps\\project_1',
 preview_url:'/api/artifact/project_1/output/map.png',
 qa:{status:failed?'failed':'completed',errors:failed?['River label could not be placed']:[],warnings:[],label_counts:{placed_rivers:failed?0:2,requested_rivers:2,placed_admin:3,requested_admin:3,placed_lake_labels_total:1,requested_lakes:1}},
 job:{schema_version:1,title,source_crs:'EPSG:4326',lake_file:'data_work/lake.geojson'},
 downloads:[{name:'Map PNG',filename:'map.png',url:'/api/artifact/project_1/output/map.png'}]
};}
w.fetch = async (path,options={}) => {
 const url = new URL(path,w.location.href); const route=url.pathname;
 const body = options.body ? JSON.parse(options.body) : null;
 calls.push({route,body,headers:options.headers});
 let data;
 if(route==='/api/status') data={version:'1.0.0-preview.1',workspace:'C:\\Maps',environment:{status:'ready',executable:'C:\\App\\python.exe'},projects:[{id:'project_1',title:'Existing Map'}],examples:[{id:'shijiu',title:'Shijiu Lake Example',description:'Open-data example'}]};
 else if(route==='/api/search') data={results:[{id:'1',name:'Chaohu Lake, Anhui',bbox:[117,31,118,32],bbox_inferred:true,osm_type:'relation',osm_id:123,type:'lake'}]};
 else if(['/api/create','/api/example','/api/import','/api/rerender'].includes(route)) {
  const id='task_'+(++taskNumber); const failed=route==='/api/create';
  tasks[id]={status:failed?'failed':'completed',progress:100,message:failed?'Diagnostic preview generated':'Completed',error:failed?'River label could not be placed':null,logs:['Reading data','Completed'],result:result(failed,body.title||'Example Map')};
  data={task_id:id};
 } else if(route.startsWith('/api/task/')) data=tasks[route.split('/').pop()];
 else if(route.startsWith('/api/artifact/')) return {ok:true,status:200,blob:async()=>new w.Blob(['image'],{type:'image/png'})};
 else if(route.startsWith('/api/projects/')) data=result();
 else throw new Error('unexpected route '+route);
 return {ok:true,status:200,text:async()=>JSON.stringify(data)};
};
const sleep=()=>new Promise(r=>setTimeout(r,20));
const click=id=>d.getElementById(id).click();
const submit=id=>d.getElementById(id).dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
(async()=>{
 w.eval(script); await sleep();
 assert.equal(d.getElementById('connection-label').textContent,'Local app connected');
 assert.equal(d.querySelectorAll('.example-card').length,1);
 d.getElementById('map-query').value='Chaohu Lake, Anhui'; click('search-location'); await sleep();
 d.querySelector('.search-result').click();
 d.getElementById('admin-queries').value='Gaochun District, Nanjing\nLishui District, Nanjing';
 assert.ok(d.getElementById('confirm-estimated-bbox'));
 submit('online-form'); await sleep();
 assert.equal(calls.filter(c=>c.route==='/api/create').length,0,'estimated bbox needs explicit confirm');
 d.getElementById('confirm-estimated-bbox').checked=true;
 submit('online-form'); await sleep(); await sleep();
 const create=calls.find(c=>c.route==='/api/create');
 assert.equal(create.body.selected_place.osm_id,123);
 assert.deepEqual(Array.from(create.body.admin_queries),['Gaochun District, Nanjing','Lishui District, Nanjing'],'commas within qualified English place names must be retained');
 assert.equal(d.getElementById('map-preview').hidden,false,'failed task must show diagnostic preview');
 assert.equal(d.getElementById('result-badge').textContent,'Draft requires revision');
 assert.ok(d.getElementById('global-message').textContent.includes('River label could not be placed'));
 d.getElementById('revision-title').value='Updated Title'; submit('rerender-form'); await sleep(); await sleep();
 assert.equal(calls.find(c=>c.route==='/api/rerender').body.title,'Updated Title');
 assert.equal(d.getElementById('preview-title').textContent,'Updated Title');
 d.querySelector('.download-button').click(); await sleep();
 assert.equal(downloads.at(-1).name,'map.png','download should retain file extension');
 click('copy-ai-prompt'); await sleep();
 assert.ok(clipboard.includes('C:\\Maps\\project_1'));
 assert.ok(clipboard.includes('never use river-name leader lines'));
 click('tab-import');
 d.getElementById('import-title').value='Imported Map';
 submit('import-form'); await sleep();
 assert.equal(calls.filter(c=>c.route==='/api/import').length,0);
 d.getElementById('confirm-crs').checked=true;
 d.getElementById('import-admin-level').value='city';
 const geojson={type:'FeatureCollection',features:[]};
 Object.defineProperty(d.getElementById('admin-file'),'files',{value:[{name:'admin.geojson',size:40,text:async()=>JSON.stringify(geojson)}],configurable:true});
 submit('import-form'); await sleep(); await sleep();
 const imp=calls.find(c=>c.route==='/api/import');
 assert.equal(imp.body.source_crs,'EPSG:4326');
 assert.equal(imp.body.admin_level,'city');
 assert.ok(imp.body.layers.admin);
 assert.ok(calls.filter(c=>!c.route.startsWith('/api/artifact')).every(c=>c.headers['X-App-Token']==='test-token'));
 const staticIds=Array.from(script.matchAll(/\$\("([^"]+)"\)/g),m=>m[1]);
 const missing=[...new Set(staticIds)].filter(id=>!d.getElementById(id));
 assert.deepEqual(missing,[]);
 console.log(JSON.stringify({status:'passed',checks:['initial status','inferred bbox confirmation','selected_place forwarding','qualified English administrative names','failed task diagnostic preview','rerender title','download filename extension','Codex prompt','CRS confirmation','explicit admin level','request token','static element references'],scope:'jsdom with mocked API; no browser layout or real backend claimed'},null,2));
 w.close();
})().catch(error=>{console.error(error.stack);w.close();process.exitCode=1;});
