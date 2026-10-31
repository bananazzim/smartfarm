// Player-radius-expanded beds are supplied by the prototype's scene builder.
export function pointBlocked(x,z,world) {
  return x<.45 || x>world.length-.45 || z<.37 || z>world.width-.37 || world.rects.some(r=>x>r[0]&&x<r[2]&&z>r[1]&&z<r[3]);
}
export function clearSegment(a,b,world) {
  const count=Math.max(1,Math.ceil(Math.hypot(b.x-a.x,b.z-a.z)/.15));
  for(let i=1;i<=count;i++) if(pointBlocked(a.x+(b.x-a.x)*i/count,a.z+(b.z-a.z)*i/count,world)) return false;
  return true;
}
export function planRoute(start,goal,world) {
  if(pointBlocked(goal.x,goal.z,world)) return null;
  if(clearSegment(start,goal,world)) return [goal];
  const step=.2, queue=[{x:start.x,z:start.z,ix:0,iz:0,g:0,parent:null}], costs=new Map([['0,0',0]]);
  let visits=0;
  while(queue.length && visits++<16000) {
    let best=0;
    for(let i=1;i<queue.length;i++) if(queue[i].g+Math.hypot(queue[i].x-goal.x,queue[i].z-goal.z)<queue[best].g+Math.hypot(queue[best].x-goal.x,queue[best].z-goal.z)) best=i;
    const node=queue.splice(best,1)[0];
    if(Math.hypot(node.x-goal.x,node.z-goal.z)<step*1.5 && clearSegment(node,goal,world)) {
      const route=[goal];let current=node;
      while(current.parent) {route.unshift({x:current.x,z:current.z});current=current.parent;}
      // Greedily shorten only along collision-checked segments.
      const short=[];let origin=start,index=0;
      while(index<route.length) {
        let end=index;
        for(let k=index+1;k<route.length;k++) if(clearSegment(origin,route[k],world)) end=k;
        short.push(route[end]);origin=route[end];index=end+1;
      }
      return short;
    }
    for(const [dx,dz] of [[1,0],[-1,0],[0,1],[0,-1],[1,1],[1,-1],[-1,1],[-1,-1]]) {
      const ix=node.ix+dx,iz=node.iz+dz,x=start.x+ix*step,z=start.z+iz*step,key=`${ix},${iz}`,g=node.g+Math.hypot(dx,dz)*step;
      if(costs.has(key)&&costs.get(key)<=g || !clearSegment(node,{x,z},world)) continue;
      costs.set(key,g);queue.push({x,z,ix,iz,g,parent:node});
    }
  }
  return null;
}
