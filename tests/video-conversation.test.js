import test from 'node:test';
import assert from 'node:assert/strict';
import {conversationQuestion} from '../video-review-model.js';

test('Chat excludes answers from another candidate set or an unapproved response',()=>{
 const turns=[{candidate_set_id:'old',approved:true,question:'old',answer:'STALE'},
 {candidate_set_id:'current',approved:false,question:'unsafe',answer:'REJECTED'},
 {candidate_set_id:'current',approved:true,question:'Why this?',answer:'Reviewed model estimates.'}];
 const text=conversationQuestion(turns,'And the alternative?','current','pass:H02');
 assert.ok(!text.includes('STALE'));assert.ok(!text.includes('REJECTED'));
 assert.ok(text.includes('not new evidence'));assert.ok(text.includes('Reviewed model estimates.'));
 assert.ok(text.includes('Current question: And the alternative?'));
});
test('Bounded conversation keeps the complete current question',()=>{
 const turns=Array.from({length:20},()=>({candidate_set_id:'current',approved:true,question:'"'.repeat(100),answer:'\\'.repeat(120)}));
 const text=conversationQuestion(turns,'问'.repeat(600),'current','pass:H02');
 assert.ok(text.length<=1200);assert.ok(text.includes('问'.repeat(600)));
 assert.throws(()=>conversationQuestion([],'x'.repeat(601),'current'));
 assert.throws(()=>conversationQuestion([],'  ','current'));
});
