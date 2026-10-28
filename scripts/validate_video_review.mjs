import fs from 'node:fs';import Ajv2020 from 'ajv/dist/2020.js';
const schema=JSON.parse(fs.readFileSync(new URL('../contracts/video-review.schema.json',import.meta.url)));
const validate=new Ajv2020({allErrors:true,strict:true}).compile(schema);
const paths=process.argv.slice(2);for(const path of paths.length?paths:[new URL('../tests/fixtures/video-review/annotation.json',import.meta.url)]){if(!validate(JSON.parse(fs.readFileSync(path))))throw Error(JSON.stringify(validate.errors));}console.log('Manual video annotation schema: PASS');
