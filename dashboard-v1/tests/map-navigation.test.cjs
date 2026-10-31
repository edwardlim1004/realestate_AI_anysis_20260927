"use strict";
const assert=require("node:assert/strict");
const MapNavigation=require("../map-navigation.js");

function stubMap(){
 const events=new Map(),attrs=new Map();
 let captures=0;
 const svg={
  addEventListener(type,fn){events.set(type,fn);},
  setAttribute(name,val){attrs.set(name,val);},
  getBoundingClientRect(){return {width:750,height:320,left:0,top:0};},
  setPointerCapture(){captures++;},
  releasePointerCapture(){},
  hasPointerCapture(){return captures>0;},
  events,attrs,get captures(){return captures;}
 };
 return svg;
}
const map=stubMap();
const navigator=MapNavigation.createMapNavigator(map);
assert.equal(navigator.getState().zoom,1);
assert.equal(map.attrs.get("viewBox"),"0 0 600 320");
assert.equal(map.events.has("wheel"),true);
const box0=navigator.getState();
let prevented=false;
map.events.get("wheel")({deltaY:-100,clientX:400,clientY:150,preventDefault(){prevented=true;}});
assert.ok(prevented,"wheel must prevent page scroll over map");
assert.ok(navigator.getState().zoom>1,"wheel-up increases zoom");
assert.ok(navigator.getState().width<box0.width,"viewport narrows");
assert.ok(navigator.getState().x>0,"zoom follows cursor, not map origin");
const afterZoom=navigator.getState();
navigator.zoom(1e9);
assert.equal(navigator.getState().zoom,MapNavigation.MAX_ZOOM,"maximum zoom should be bounded");
navigator.zoom(.000001);
assert.equal(navigator.getState().zoom,1,"minimum zoom should be bounded");
navigator.focusBounds({x0:230,x1:255,y0:130,y1:150});
assert.ok(navigator.getState().zoom>2,"selected district focus should zoom");
const beforePan=navigator.getState();
navigator.panPixels(35,10);
assert.ok(navigator.getState().x<beforePan.x,"drag right pans content right");
navigator.reset();
assert.equal(navigator.getState().zoom,1);
assert.equal(map.attrs.get("viewBox"),"0 0 600 320");

// Short down+up is a click: pointer capture must not steal the path click.
map.events.get("pointerdown")({button:0,pointerType:"mouse",pointerId:12,clientX:250,clientY:125});
assert.equal(map.captures,0);
map.events.get("pointerup")({pointerId:12});
assert.equal(navigator.wasDragged(),false);
navigator.zoom(2);
map.events.get("pointerdown")({button:0,pointerType:"mouse",pointerId:13,clientX:350,clientY:120});
map.events.get("pointermove")({pointerId:13,clientX:385,clientY:144,preventDefault(){}});
assert.equal(map.captures,1,"capture mouse pointer only after pan begins");
map.events.get("pointerup")({pointerId:13});
assert.equal(navigator.wasDragged(),true,"suppress accidental select after dragging");
const view=navigator.getState();
assert.ok(view.x>=0&&view.y>=0&&view.x+view.width<=600.00001&&view.y+view.height<=320.00001,"pan is clipped to map bounds");
assert.equal(afterZoom.zoom>1,true);
console.log("PASS city SVG wheel zoom, zoom bounds, focus, pan, click/drag isolation");
