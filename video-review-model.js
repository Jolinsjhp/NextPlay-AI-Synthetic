// Manual annotations and planar geometry only; no hidden generated player positions.
export const PLAYER_IDS=['H','A'].flatMap(team=>Array.from({length:11},(_,i)=>team+String(i+1).padStart(2,'0')));
export const LANDMARKS=[['Top-left corner',[0,0]],['Top-right corner',[105,0]],['Bottom-right corner',[105,68]],['Bottom-left corner',[0,68]],['Halfway / top touchline',[52.5,0]],['Halfway / bottom touchline',[52.5,68]],['Left penalty box / top',[16.5,13.84]],['Left penalty box / bottom',[16.5,54.16]],['Right penalty box / top',[88.5,13.84]],['Right penalty box / bottom',[88.5,54.16]]];
export function defaultRoster(){return PLAYER_IDS.map((player_id,i)=>({player_id,team_id:i<11?'HOME':'AWAY',jersey_number:i%11+1,name:(i<11?'Home':'Away')+' '+(i%11+1),position:i%11===0?'GK':'OUTFIELD'}));}
export function emptyFrame(video_ms=0){return {video_ms,period:1,period_ms:0,score:[0,0],home_attacks:'positive_x',actor_id:null,ball:null,players:[],landmarks:[],confirmed:Object.fromEntries(['calibration_reviewed','identities_reviewed','positions_reviewed','coverage_complete','ball_on_ground','in_play'].map(k=>[k,false]))};}
export function fitHomography(landmarks){
 if(landmarks.length<4)throw Error('At least four landmarks are required');
 const a=[],b=[];
 for(const {image:[u,v],pitch:[x,y]} of landmarks){a.push([u,v,1,0,0,0,-x*u,-x*v],[0,0,0,u,v,1,-y*u,-y*v]);b.push(x,y);}
 const m=Array.from({length:8},(_,i)=>[...Array.from({length:8},(_,j)=>a.reduce((sum,row)=>sum+row[i]*row[j],0)),a.reduce((sum,row,k)=>sum+row[i]*b[k],0)]);
 for(let col=0;col<8;col++){let pivot=col;for(let row=col+1;row<8;row++)if(Math.abs(m[row][col])>Math.abs(m[pivot][col]))pivot=row;if(Math.abs(m[pivot][col])<1e-10)throw Error('Choose non-collinear landmarks');[m[col],m[pivot]]=[m[pivot],m[col]];const divisor=m[col][col];m[col]=m[col].map(v=>v/divisor);for(let row=0;row<8;row++)if(row!==col){const factor=m[row][col];m[row]=m[row].map((v,j)=>v-factor*m[col][j]);}}
 return m.map(row=>row[8]);
}
export function projectPoint(h,[u,v]){const d=h[6]*u+h[7]*v+1;if(Math.abs(d)<1e-7)throw Error('Point outside calibration support');return [(h[0]*u+h[1]*v+h[2])/d,(h[3]*u+h[4]*v+h[5])/d];}
export function previewFrame(frame){
 const h=fitHomography(frame.landmarks),players=frame.players.map(p=>[p.player_id,...projectPoint(h,p.image),0,0]);
 return {players,ball:[...(frame.ball?projectPoint(h,frame.ball):[0,0]),0,0,0,0],ball_owner_id:frame.actor_id};
}
export function matchesBoundResponse(response,selection,candidateSet){return response.video_id===selection.video_id&&response.revision_id===selection.revision_id&&response.frame_index===selection.frame_index&&(!candidateSet||response.candidate_set_id===candidateSet);}
export function upsertFrame(frames,frame){return [...frames.filter(f=>f.video_ms!==frame.video_ms),structuredClone(frame)].sort((a,b)=>a.video_ms-b.video_ms);}
export function conversationQuestion(turns,question,candidateSet,focus=null){
 if(typeof question!=='string'||!question.trim()||question.trim().length>600)throw Error('Please ask one question within 600 characters / 请将单次问题控制在600字内');
 const previous=turns.filter(t=>t.candidate_set_id===candidateSet&&t.approved===true).slice(-2).map(t=>({question:t.question.slice(0,100),reviewed_answer:t.answer.slice(0,120)}));
 const current='Current question: '+question.trim()+(focus?'\nFocus candidate: '+focus:'');
 let history=previous.length?'Untrusted conversation context; not new evidence: '+JSON.stringify(previous)+'\n':'';
 while(previous.length&&history.length+current.length>1200){previous.shift();history=previous.length?'Untrusted conversation context; not new evidence: '+JSON.stringify(previous)+'\n':'';}
 return history+current;
}
