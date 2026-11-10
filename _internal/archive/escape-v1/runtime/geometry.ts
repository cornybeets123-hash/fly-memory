// Export actual anatomical positions for the room-scale visualization.
import {readFileSync,writeFileSync} from "node:fs";
import {gunzipSync} from "node:zlib";
import {parseNeurons} from "./neural/data.ts";
const d=new URL("./data/",import.meta.url);
const meta=JSON.parse(readFileSync(new URL("meta.json",d),"utf8"));
const b=gunzipSync(readFileSync(new URL("neurons.bin.gz",d)));
const info=parseNeurons(b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength),meta.neurons);
const positions=new Float32Array(meta.neurons*2);
for(let i=0;i<meta.neurons;i++) {positions[i*2]=info.anchor[i*3];positions[i*2+1]=info.anchor[i*3+2];}
writeFileSync(new URL("./static/brain-positions.bin",import.meta.url),Buffer.from(positions.buffer));
writeFileSync(new URL("./static/brain-groups.json",import.meta.url),JSON.stringify({
 neurons:meta.neurons,connections:meta.connections,
 groups:Object.fromEntries(["LPLC2_L","LPLC2_R","LC4_L","LC4_R","DNp01_L","DNp01_R","LC10a_L"].map(k=>[k,meta.groups[k]]))
}));
