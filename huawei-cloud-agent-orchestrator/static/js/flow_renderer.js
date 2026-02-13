/**
 * 流程图渲染引擎（共享模块）
 * 用法: FlowRenderer.render(canvasElement, workflowObj)
 */
var FlowRenderer = (function() {
    var stateMap = new WeakMap();

    function esc(s) { var d=document.createElement('div'); d.textContent=s||''; return d.innerHTML; }

    function topoLayers(tasks) {
        var nm={}; tasks.forEach(function(t,i){nm[t.name]=i;});
        var dep=new Array(tasks.length).fill(-1);
        function gd(i){
            if(dep[i]>=0)return dep[i]; var t=tasks[i];
            var ds=(t.depends_on||[]).filter(function(d){return nm[d]!==undefined;});
            if(!ds.length){dep[i]=0;return 0;} var mx=0;
            ds.forEach(function(d){var v=gd(nm[d]);if(v>mx)mx=v;}); dep[i]=mx+1; return dep[i];
        }
        tasks.forEach(function(_,i){gd(i);});
        var md=0; dep.forEach(function(d){if(d>md)md=d;});
        var ly=[]; for(var l=0;l<=md;l++)ly.push([]);
        tasks.forEach(function(_,i){ly[dep[i]].push(i);});
        return {layers:ly,nameMap:nm};
    }

    function nodeDrag(node,idx,st) {
        var drag=false,ox=0,oy=0; node.style.cursor='grab';
        node.addEventListener('mousedown',function(e){
            if(!st)return; e.preventDefault(); drag=true;
            node.style.cursor='grabbing'; node.style.zIndex='10';
            ox=e.clientX-node.offsetLeft; oy=e.clientY-node.offsetTop;
            function mv(ev){if(!drag)return;
                var nx=Math.max(0,ev.clientX-ox),ny=Math.max(0,ev.clientY-oy);
                node.style.left=nx+'px'; node.style.top=ny+'px';
                var p=st.pos[idx],w=st.nW,h=st.nH;
                p.x=nx;p.y=ny;p.cx=nx+w/2;p.cy=ny+h/2;p.top=ny;p.bottom=ny+h;p.left=nx;p.right=nx+w;
                reDraw(st);}
            function up(){drag=false;node.style.cursor='grab';node.style.zIndex='2';
                document.removeEventListener('mousemove',mv);document.removeEventListener('mouseup',up);}
            document.addEventListener('mousemove',mv);document.addEventListener('mouseup',up);
        });
    }

    function markerDrag(div,key,st) {
        var drag=false,ox=0,oy=0; div.style.cursor='grab';
        div.addEventListener('mousedown',function(e){
            if(!st)return; e.preventDefault(); drag=true; div.style.cursor='grabbing';
            ox=e.clientX-div.offsetLeft; oy=e.clientY-div.offsetTop;
            function mv(ev){if(!drag)return;
                var nx=Math.max(0,ev.clientX-ox),ny=Math.max(0,ev.clientY-oy);
                div.style.left=nx+'px'; div.style.top=ny+'px';
                if(key==='start'){st.sCx=nx+st.mW/2;st.sB=ny+st.mH;}
                else{st.eCx=nx+st.mW/2;st.eT=ny;}
                reDraw(st);}
            function up(){drag=false;div.style.cursor='grab';
                document.removeEventListener('mousemove',mv);document.removeEventListener('mouseup',up);}
            document.addEventListener('mousemove',mv);document.addEventListener('mouseup',up);
        });
    }

    function reDraw(s) {
        if(!s)return;
        var old=s.cv.querySelector('svg.flow-lines'); if(old)old.remove();
        var mx=400,my=400;
        for(var k in s.pos){var p=s.pos[k];if(p.right>mx)mx=p.right;if(p.bottom>my)my=p.bottom;}
        svgLines(s.cv,s.tasks,s.layers,s.pos,s.nameMap,mx+100,my+100,s.sCx,s.sB,s.eCx,s.eT);
    }

    function svgLines(cv,tasks,layers,pos,nm,sw,sh,sCx,sB,eCx,eT) {
        var ns='http://www.w3.org/2000/svg';
        var svg=document.createElementNS(ns,'svg');
        svg.setAttribute('class','flow-lines'); svg.setAttribute('width',sw); svg.setAttribute('height',sh);
        var defs=document.createElementNS(ns,'defs');
        var mk=document.createElementNS(ns,'marker');
        mk.setAttribute('id','ah'); mk.setAttribute('markerWidth','8'); mk.setAttribute('markerHeight','6');
        mk.setAttribute('refX','8'); mk.setAttribute('refY','3'); mk.setAttribute('orient','auto');
        var pl=document.createElementNS(ns,'polygon');
        pl.setAttribute('points','0 0,8 3,0 6'); pl.setAttribute('fill','#0d6efd');
        mk.appendChild(pl); defs.appendChild(mk); svg.appendChild(defs);
        function ln(x1,y1,x2,y2){
            var p=document.createElementNS(ns,'path');
            var my=y1+(y2-y1)*0.5;
            p.setAttribute('d','M '+x1+' '+y1+' C '+x1+' '+my+', '+x2+' '+my+', '+x2+' '+y2);
            p.setAttribute('fill','none'); p.setAttribute('stroke','#0d6efd');
            p.setAttribute('stroke-width','2'); p.setAttribute('marker-end','url(#ah)');
            p.setAttribute('opacity','0.6'); svg.appendChild(p);
        }
        cv.insertBefore(svg,cv.firstChild);
        layers[0].forEach(function(i){var p=pos[i]; ln(sCx,sB,p.cx,p.top);});
        tasks.forEach(function(t,i){
            (t.depends_on||[]).filter(function(d){return nm[d]!==undefined;}).forEach(function(dn){
                var f=pos[nm[dn]],to=pos[i]; if(f&&to) ln(f.cx,f.bottom,to.cx,to.top);
            });
        });
        layers[layers.length-1].forEach(function(i){var p=pos[i]; ln(p.cx,p.bottom,eCx,eT);});
    }

    function render(canvasEl, workflow) {
        var cv = typeof canvasEl === 'string' ? document.getElementById(canvasEl) : canvasEl;
        if (!cv) return;
        cv.innerHTML = '';

        var tasks = (workflow && workflow.tasks) || [];
        if (!tasks.length) {
            cv.innerHTML = '<div class="text-center text-muted py-4">无任务</div>';
            return;
        }

        var topo = topoLayers(tasks);
        var layers = topo.layers, nameMap = topo.nameMap;

        var nW = 210, nH = 110, gX = 60, gY = 50;
        var padL = 50, padT = 50, mH = 36, mW = 72;

        var maxInLayer = 1;
        layers.forEach(function(l) { if (l.length > maxInLayer) maxInLayer = l.length; });

        var totalW = padL * 2 + maxInLayer * nW + (maxInLayer - 1) * gX;
        var totalH = padT + mH + gY + layers.length * (nH + gY) + mH + gY;

        cv.style.width = Math.max(totalW, 400) + 'px';
        cv.style.height = totalH + 'px';

        var pos = {};

        // Start marker
        var sX = totalW / 2 - mW / 2, sY = padT;
        var startDiv = document.createElement('div');
        startDiv.className = 'flow-marker start';
        startDiv.style.left = sX + 'px';
        startDiv.style.top = sY + 'px';
        startDiv.innerHTML = '<i class="fas fa-play me-1"></i>Start';
        cv.appendChild(startDiv);

        // Task nodes by layer — collect for deferred drag binding
        var curY = sY + mH + gY;
        var nodeRefs = [];
        layers.forEach(function(layer) {
            var lW = layer.length * nW + (layer.length - 1) * gX;
            var offX = (totalW - lW) / 2;
            layer.forEach(function(idx, col) {
                var t = tasks[idx];
                var x = offX + col * (nW + gX), y = curY;
                pos[idx] = {
                    x:x, y:y, cx:x+nW/2, cy:y+nH/2,
                    top:y, bottom:y+nH, left:x, right:x+nW
                };
                var node = document.createElement('div');
                node.className = 'flow-node';
                node.style.left = x+'px'; node.style.top = y+'px'; node.style.width = nW+'px';
                var svc = esc((t.service||'').toUpperCase());
                var op = esc(t.operation||'');
                var desc = t.description ? '<div class="fn-desc">'+esc(t.description)+'</div>' : '';
                node.innerHTML =
                    '<div class="flow-node-head">' +
                        '<span class="step-badge">'+(idx+1)+'</span>' +
                        '<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">'+svc+'</span>' +
                    '</div>' +
                    '<div class="flow-node-body">' +
                        '<div class="fn-name">'+esc(t.name)+'</div>' +
                        '<div class="fn-svc"><i class="fas fa-cog me-1"></i>'+svc+' &rarr; '+op+'</div>' +
                        desc +
                    '</div>';
                cv.appendChild(node);
                nodeRefs.push({node:node, idx:idx});
            });
            curY += nH + gY;
        });

        // End marker
        var eX = totalW / 2 - mW / 2, eY = curY;
        var endDiv = document.createElement('div');
        endDiv.className = 'flow-marker end';
        endDiv.style.left = eX + 'px';
        endDiv.style.top = eY + 'px';
        endDiv.innerHTML = 'End <i class="fas fa-stop ms-1"></i>';
        cv.appendChild(endDiv);

        // Build state object
        var st = {
            cv:cv, tasks:tasks, layers:layers, pos:pos, nameMap:nameMap,
            nW:nW, nH:nH, mW:mW, mH:mH,
            sCx:sX+mW/2, sB:sY+mH,
            eCx:eX+mW/2, eT:eY
        };
        stateMap.set(cv, st);

        // Bind node drag (deferred — st is now defined)
        nodeRefs.forEach(function(r) { nodeDrag(r.node, r.idx, st); });

        // Bind marker drag
        markerDrag(startDiv, 'start', st);
        markerDrag(endDiv, 'end', st);

        // Update canvas height and draw lines
        cv.style.height = (eY + mH + padT) + 'px';
        reDraw(st);
    }

    return { render: render, escHtml: esc };
})();
