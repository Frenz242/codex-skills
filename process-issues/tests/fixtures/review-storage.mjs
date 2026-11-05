import {DatabaseSync} from 'node:sqlite';
export function storage(){
 const sql=new DatabaseSync(':memory:');
 sql.exec('CREATE TABLE publications(publication_key TEXT PRIMARY KEY,pr_key TEXT,project_key TEXT,manifest TEXT,created_at TEXT);CREATE TABLE reviews(pr_key TEXT PRIMARY KEY,project_key TEXT,repository TEXT,pr_number INTEGER,version INTEGER,current_key TEXT,observation TEXT,updated_at TEXT)');
 const wrap=(query,args=[])=>({bind(...values){return wrap(query,values)},async first(){return sql.prepare(query).get(...args)||null},async all(){return {results:sql.prepare(query).all(...args)}},run(){return {meta:{changes:Number(sql.prepare(query).run(...args).changes)}}}});
 const db={prepare:q=>wrap(q),fail:false,async batch(list){if(this.fail)throw Error('synthetic DB outage');sql.exec('BEGIN');try{const results=[];for(const s of list)results.push(s.run());sql.exec('COMMIT');return results;}catch(e){sql.exec('ROLLBACK');throw e;}}};
 const objects=new Map(),bucket={fail:false,async put(k,b){if(this.fail)throw Error('synthetic R2 outage');objects.set(k,new Uint8Array(b));},async head(k){return objects.has(k)?{}:null;},async get(k,o){const b=objects.get(k);return b?{body:b.slice(o.range.offset,o.range.offset+o.range.length)}:null;}};
 return {DB:db,BUCKET:bucket,REVIEW_PUBLISHER_KEY:'synthetic-writer-key',objects,close:()=>sql.close()};
}
