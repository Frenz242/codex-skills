import {publicationKey} from '../../scripts/review-bundle.mjs';
export async function fixture() {
  const repository={host:'github.example',id:101,owner:'sample',name:'widget',url:'https://github.example/sample/widget'};
  const sha='a'.repeat(40),at='2026-01-01T00:00:00Z';
  const m={schema_version:1,repository,pull_request:{number:7,title:'Synthetic output comparison',url:repository.url+'/pull/7',issues:[repository.url+'/issues/3'],head:{repository,ref:'fix/output'},base:{repository,ref:'main'}},
    revision:{head_sha:sha,base_sha:'b'.repeat(40),captured_at:at,clean_source:true,build_sha:null},
    observed_github:{head_sha:sha,state:'open',draft:true,observed_at:at,reviews:'unknown',checks:'unknown'},
    summary:{changed:'Synthetic serializer output fixture',why:'Demonstrate the nonvisual bundle contract',inspect:'Compare the recorded output; this fixture is not live verification'},
    acceptance:[{criterion:'Synthetic output check',state:'verified',automated:[{result:'passed',description:'Synthetic fixture assertion',reason:''}],runtime:[],output:[],delivery:[],limitation:''}],
    demonstration:{kind:'nonvisual',surface:'nonvisual',capture_source:'none',state:'not applicable',scenario:'Synthetic serializer comparison',outcome:'Expected output is documented in the fixture',tool:'synthetic fixture',source_sha:sha,limitation:'No UI; no video is needed'},
    assets:[],publication:{key:'',expected_current_version:0,prepared_at:at}};
  m.publication.key=await publicationKey(m);return m;
}
