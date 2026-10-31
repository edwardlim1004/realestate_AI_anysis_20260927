/* Interactive SVG navigation. No third-party map library or location service. */
(function(root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  if (root) root.MapNavigation = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function() {
  "use strict";

  const BASE = Object.freeze({x:0, y:0, width:600, height:320});
  const MAX_ZOOM = 8;
  const clamp = (n, a, b) => Math.max(a, Math.min(b, n));
  const finite = (x, fallback=0) => Number.isFinite(Number(x)) ? Number(x) : fallback;

  function boundedView(view) {
    const width = clamp(finite(view.width, BASE.width), BASE.width/MAX_ZOOM, BASE.width);
    const height = width * BASE.height / BASE.width;
    return {
      x: clamp(finite(view.x), BASE.x, BASE.width-width),
      y: clamp(finite(view.y), BASE.y, BASE.height-height),
      width, height
    };
  }

  function createMapNavigator(svg, options={}) {
    if (!svg || typeof svg.addEventListener!=="function") throw new Error("SVG map element required");
    let view = {...BASE};
    let drag = null;
    let suppressClickUntil = 0;
    const onChange = typeof options.onChange === "function" ? options.onChange : () => {};
    const getState = () => ({...view, zoom:BASE.width/view.width});

    function update(next) {
      const v=boundedView(next);
      if (![v.x,v.y,v.width,v.height].every(Number.isFinite)) return;
      view=v;
      svg.setAttribute("viewBox", [v.x,v.y,v.width,v.height].map(n=>Number(n.toFixed(5))).join(" "));
      onChange(getState());
    }

    function centerOfView() {
      return {x:view.x+view.width/2, y:view.y+view.height/2};
    }

    function localSvgPoint(clientX, clientY) {
      // getScreenCTM includes the SVG's xMidYMid/meet letterboxing.
      if (typeof svg.createSVGPoint==="function" && typeof svg.getScreenCTM==="function") {
        const matrix=svg.getScreenCTM();
        if (matrix && typeof matrix.inverse==="function") {
          const point=svg.createSVGPoint();
          point.x=clientX;point.y=clientY;
          const transformed=point.matrixTransform(matrix.inverse());
          if (Number.isFinite(transformed.x) && Number.isFinite(transformed.y)) return transformed;
        }
      }
      // Fallback for test environments or older browsers with no SVG matrices.
      const rect=svg.getBoundingClientRect();
      if (!(rect.width>0 && rect.height>0)) return centerOfView();
      const scale=Math.min(rect.width/view.width,rect.height/view.height);
      const offsetX=(rect.width-view.width*scale)/2;
      const offsetY=(rect.height-view.height*scale)/2;
      return {
        x:view.x+(clientX-rect.left-offsetX)/scale,
        y:view.y+(clientY-rect.top-offsetY)/scale
      };
    }

    function zoom(factor, anchor=centerOfView()) {
      if (!Number.isFinite(factor) || factor<=0) return getState();
      const nextZoom=clamp(BASE.width/view.width*factor,1,MAX_ZOOM);
      const w=BASE.width/nextZoom;
      const h=BASE.height/nextZoom;
      const fx=(anchor.x-view.x)/view.width;
      const fy=(anchor.y-view.y)/view.height;
      update({x:anchor.x-fx*w, y:anchor.y-fy*h, width:w, height:h});
      return getState();
    }

    function panPixels(deltaX,deltaY) {
      const rect=svg.getBoundingClientRect();
      if (!rect.width || !rect.height) return getState();
      const pixelsPerUnit=Math.min(rect.width/view.width,rect.height/view.height);
      update({...view,x:view.x-deltaX/pixelsPerUnit,y:view.y-deltaY/pixelsPerUnit});
      return getState();
    }

    function reset() { drag=null;update(BASE);return getState(); }

    function focusBounds(bounds,padding=1.55) {
      const x0=finite(bounds?.x0,NaN), x1=finite(bounds?.x1,NaN);
      const y0=finite(bounds?.y0,NaN), y1=finite(bounds?.y1,NaN);
      if (![x0,x1,y0,y1].every(Number.isFinite) || x1<x0 || y1<y0) return getState();
      const w=Math.max(12,(x1-x0)*padding),h=Math.max(12,(y1-y0)*padding);
      const targetZoom=clamp(Math.min(BASE.width/w,BASE.height/h),1,MAX_ZOOM);
      const nextWidth=BASE.width/targetZoom,nextHeight=BASE.height/targetZoom;
      update({x:(x0+x1)/2-nextWidth/2,y:(y0+y1)/2-nextHeight/2,width:nextWidth,height:nextHeight});
      return getState();
    }

    function onWheel(event) {
      if (typeof event.preventDefault==="function") event.preventDefault();
      const dy=clamp(finite(event.deltaY),-150,150);
      if (dy===0) return;
      zoom(Math.exp(-dy*.0027),localSvgPoint(event.clientX,event.clientY));
    }

    function onPointerDown(event) {
      if (event.pointerType==="touch" || event.button!==0) return;
      drag={id:event.pointerId,x:event.clientX,y:event.clientY,prevX:event.clientX,prevY:event.clientY,moved:false};
      // Do not capture on pointerdown: a normal path click must select its district.
      // Capture only after the pointer has actually moved into a drag.
    }
    function onPointerMove(event) {
      if (!drag || event.pointerId!==drag.id) return;
      const distance=Math.hypot(event.clientX-drag.x,event.clientY-drag.y);
      if (distance>5 && !drag.moved) {
        drag.moved=true;
        if (typeof svg.setPointerCapture==="function") {
          try { svg.setPointerCapture(event.pointerId); } catch (_) {}
        }
      }
      if (drag.moved) {
        panPixels(event.clientX-drag.prevX,event.clientY-drag.prevY);
        if (typeof event.preventDefault==="function") event.preventDefault();
      }
      drag.prevX=event.clientX;drag.prevY=event.clientY;
    }
    function finishPointer(event) {
      if (!drag || event.pointerId!==drag.id) return;
      if (drag.moved) suppressClickUntil=Date.now()+250;
      if (typeof svg.releasePointerCapture==="function") {
        try { if (typeof svg.hasPointerCapture!=="function" || svg.hasPointerCapture(event.pointerId)) svg.releasePointerCapture(event.pointerId); } catch (_) {}
      }
      drag=null;
    }
    function wasDragged() { return !!(drag?.moved) || Date.now()<suppressClickUntil; }
    svg.addEventListener("wheel",onWheel,{passive:false});
    svg.addEventListener("pointerdown",onPointerDown);
    svg.addEventListener("pointermove",onPointerMove);
    svg.addEventListener("pointerup",finishPointer);
    svg.addEventListener("pointercancel",finishPointer);
    svg.addEventListener("lostpointercapture",finishPointer);
    update(BASE);

    return {getState,zoom,panPixels,reset,focusBounds,wasDragged};
  }
  return {createMapNavigator,boundedView,BASE,MAX_ZOOM};
});