/* SPDX-License-Identifier: MIT
 * Event-driven RandR policy: laptop panel primary; connected displays to its right.
 * No periodic queries, external utilities, or desktop-environment dependencies.
 */
#include <X11/Xlib.h>
#include <X11/extensions/Xrandr.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <unistd.h>

#define LIMIT 64
static Display *d;
static Window root;
static int xerror;
static int on_error(Display *display, XErrorEvent *event) {
    (void)display; (void)event; xerror=1; return 0;
}
typedef struct {
    RROutput id;
    XRROutputInfo *info;
    RRMode mode;
    RRCrtc crtc;
    int x,y,w,h;
} Output;
static int non_desktop(RROutput output) {
    Atom type;int format;unsigned long n,left;unsigned char *value=NULL;
    int result=0;
    if(XRRGetOutputProperty(d,output,XInternAtom(d,"non-desktop",False),0,1,False,False,
                           AnyPropertyType,&type,&format,&n,&left,&value)==Success && value && format==32 && n)
        result=*(unsigned long *)value!=0;
    if(value)XFree(value);
    return result;
}
static int internal(const XRROutputInfo *o) {
    return !strncmp(o->name,"eDP",3) || !strncmp(o->name,"LVDS",4) ||
           !strncmp(o->name,"DSI",3) || !strncmp(o->name,"LCD",3);
}
static XRRModeInfo *mode_info(XRRScreenResources *r, RRMode id) {
    for(int i=0;i<r->nmode;i++) if(r->modes[i].id==id) return &r->modes[i];
    return NULL;
}
static int crtc_index(XRRScreenResources *r,RRCrtc id) {
    for(int i=0;i<r->ncrtc;i++) if(r->crtcs[i]==id) return i;
    return -1;
}
/* Bipartite matching handles outputs that share limited possible CRTCs. */
static int assign(XRRScreenResources *r,Output *out,int i,int *owner,int *seen) {
    XRROutputInfo *o=out[i].info;
    for(int pass=0;pass<2;pass++) for(int k=0;k<o->ncrtc;k++) {
        RRCrtc id=o->crtcs[k];
        if((pass==0)!=(id==o->crtc)) continue;
        int c=crtc_index(r,id);
        if(c<0 || seen[c]) continue;
        seen[c]=1;
        if(owner[c]<0 || assign(r,out,owner[c],owner,seen)) {
            owner[c]=i;out[i].crtc=id;return 1;
        }
    }
    return 0;
}
static int same(XRRCrtcInfo *a,Output *b) {
    return a && a->mode==b->mode && a->x==b->x && a->y==b->y &&
           a->rotation==RR_Rotate_0 && a->noutput==1 && a->outputs[0]==b->id;
}
static void screen_size(int w,int h,int oldw,int oldh,int mmw,int mmh) {
    int mw=mmw>0 ? (int)((long)w*mmw/oldw) : w*254/960;
    int mh=mmh>0 ? (int)((long)h*mmh/oldh) : h*254/960;
    XRRSetScreenSize(d,root,w,h,mw>0?mw:1,mh>0?mh:1);XSync(d,False);
}
static unsigned long *prop(Window w,const char *name,unsigned long *n) {
    Atom type;int format;unsigned long left;unsigned char *value=NULL;
    *n=0;
    if(XGetWindowProperty(d,w,XInternAtom(d,name,False),0,4096,False,AnyPropertyType,
                          &type,&format,n,&left,&value)!=Success || format!=32) {
        if(value)XFree(value);
        *n=0;return NULL;
    }
    return (unsigned long *)value;
}
static void recover_windows(Output *out,int n,int width,int height) {
    unsigned long count,*clients=prop(root,"_NET_CLIENT_LIST",&count);
    Atom dock=XInternAtom(d,"_NET_WM_WINDOW_TYPE_DOCK",False),desktop=XInternAtom(d,"_NET_WM_WINDOW_TYPE_DESKTOP",False);
    Atom fullscreen=XInternAtom(d,"_NET_WM_STATE_FULLSCREEN",False),maxv=XInternAtom(d,"_NET_WM_STATE_MAXIMIZED_VERT",False),maxh=XInternAtom(d,"_NET_WM_STATE_MAXIMIZED_HORZ",False);
    for(unsigned long i=0;i<count;i++) {
        Window w=clients[i];unsigned long k,*p=prop(w,"_NET_WM_WINDOW_TYPE",&k);int skip=0;
        for(unsigned long j=0;j<k;j++)if(p[j]==dock || p[j]==desktop)skip=1;
        if(p)XFree(p);
        p=prop(w,"_NET_WM_STATE",&k);
        for(unsigned long j=0;j<k;j++)if(p[j]==fullscreen || p[j]==maxv || p[j]==maxh)skip=1;
        if(p)XFree(p);
        if(skip)continue;
        XWindowAttributes a;Window child;int x,y;
        if(!XGetWindowAttributes(d,w,&a) || !XTranslateCoordinates(d,w,root,0,0,&x,&y,&child))continue;
        p=prop(w,"_NET_FRAME_EXTENTS",&k);int l=0,r=0,t=0,b=0;
        if(k==4){l=p[0];r=p[1];t=p[2];b=p[3];}
        if(p)XFree(p);
        int left=x-l,top=y-t,ww=a.width+l+r,hh=a.height+t+b;
        if(left>=0 && top>=0 && left+ww<=width && top+hh<=height)continue;
        int chosen=0;long best=-1;
        for(int j=0;j<n;j++) {
            int ax=left>out[j].x?left:out[j].x,ay=top>out[j].y?top:out[j].y;
            int bx=left+ww<out[j].x+out[j].w?left+ww:out[j].x+out[j].w;
            int by=top+hh<out[j].y+out[j].h?top+hh:out[j].y+out[j].h;
            long area=bx>ax && by>ay?(long)(bx-ax)*(by-ay):0;
            if(area>best){best=area;chosen=j;}
        }
        int minx=out[chosen].x,miny=out[chosen].y;
        int maxx=minx+out[chosen].w-ww,maxy=miny+out[chosen].h-hh;
        /* Respect the primary work area if the user adds a panel or dock. */
        if(chosen==0) {
            unsigned long dn,*desk=prop(root,"_NET_CURRENT_DESKTOP",&dn),index=dn?desk[0]:0;
            if(desk)XFree(desk);
            unsigned long an,*area=prop(root,"_NET_WORKAREA",&an);
            if(index<an/4 && (int)area[index*4+1]>miny)miny=area[index*4+1];
            if(area)XFree(area);
        }
        if(maxx<minx)maxx=minx;
        if(maxy<miny)maxy=miny;
        int nx=left<minx?minx:left>maxx?maxx:left,ny=top<miny?miny:top>maxy?maxy:top;
        XEvent e={0};e.xclient.type=ClientMessage;e.xclient.window=w;
        e.xclient.message_type=XInternAtom(d,"_NET_MOVERESIZE_WINDOW",False);e.xclient.format=32;
        e.xclient.data.l[0]=NorthWestGravity|(3<<8)|(2<<12);e.xclient.data.l[1]=nx;e.xclient.data.l[2]=ny;
        XSendEvent(d,root,False,SubstructureRedirectMask|SubstructureNotifyMask,&e);
    }
    if(clients)XFree(clients);
    XFlush(d);
}
static int apply(void) {
    XRRScreenResources *r=XRRGetScreenResourcesCurrent(d,root);
    if(!r) return 1;
    if(r->noutput>LIMIT || r->ncrtc>LIMIT) { XRRFreeScreenResources(r);return 1; }
    Output out[LIMIT]={0};int n=0,result=1;
    RROutput previous_primary=XRRGetOutputPrimary(d,root);
    for(int i=0;i<r->noutput;i++) {
        XRROutputInfo *o=XRRGetOutputInfo(d,r,r->outputs[i]);
        if(o && o->connection==RR_Connected && o->nmode>0 && !non_desktop(r->outputs[i])) {
            out[n].id=r->outputs[i];out[n++].info=o;
        } else if(o) XRRFreeOutputInfo(o);
    }
    if(!n) { result=0;goto done; }
    if(n>r->ncrtc) goto done;
    int first=0;
    for(int i=0;i<n;i++) if(out[i].id==previous_primary) first=i;
    for(int i=0;i<n;i++) if(internal(out[i].info)) { first=i;break; }
    Output swap=out[0];out[0]=out[first];out[first]=swap;
    int minw,minh,maxw,maxh;
    if(!XRRGetScreenSizeRange(d,root,&minw,&minh,&maxw,&maxh)) goto done;
    int width=0,height=0;
    for(int i=0;i<n;i++) {
        /* Mode order is preferred first; choose a smaller advertised mode only
         * when needed to stay within the server's framebuffer limit. */
        XRRModeInfo *m=NULL;
        for(int j=0;j<out[i].info->nmode;j++) {
            XRRModeInfo *candidate=mode_info(r,out[i].info->modes[j]);
            if(candidate && candidate->width<=(unsigned)(maxw-width) && candidate->height<=(unsigned)maxh) {
                m=candidate;break;
            }
        }
        if(!m) goto done;
        out[i].mode=m->id;out[i].x=width;out[i].y=0;
        out[i].w=m->width;out[i].h=m->height;
        width+=out[i].w;if(out[i].h>height)height=out[i].h;
    }
    if(width<minw)width=minw;
    if(height<minh)height=minh;
    int owner[LIMIT],seen[LIMIT];
    for(int i=0;i<r->ncrtc;i++)owner[i]=-1;
    for(int i=0;i<n;i++) {
        memset(seen,0,sizeof(seen));
        if(!assign(r,out,i,owner,seen))goto done;
    }
    XWindowAttributes wa;
    if(!XGetWindowAttributes(d,root,&wa))goto done;
    int oldw=wa.width,oldh=wa.height;
    int mmw=DisplayWidthMM(d,DefaultScreen(d)),mmh=DisplayHeightMM(d,DefaultScreen(d));
    XRRCrtcInfo *saved[LIMIT]={0};
    for(int i=0;i<r->ncrtc;i++) {
        saved[i]=XRRGetCrtcInfo(d,r,r->crtcs[i]);
        if(!saved[i]) {
            for(int j=0;j<i;j++)XRRFreeCrtcInfo(saved[j]);
            goto done;
        }
    }
    XGrabServer(d);xerror=0;
    int groww=oldw>width?oldw:width,growh=oldh>height?oldh:height;
    if(groww!=oldw || growh!=oldh)screen_size(groww,growh,oldw,oldh,mmw,mmh);
    int failed=xerror;
    for(int c=0;c<r->ncrtc && !failed;c++) {
        int i=owner[c];
        if(saved[c]->mode && (i<0 || !same(saved[c],&out[i])))
            failed=XRRSetCrtcConfig(d,r,r->crtcs[c],CurrentTime,0,0,None,RR_Rotate_0,NULL,0)!=RRSetConfigSuccess;
    }
    for(int i=0;i<n && !failed;i++) {
        int c=crtc_index(r,out[i].crtc);
        if(!same(saved[c],&out[i]))
            failed=XRRSetCrtcConfig(d,r,out[i].crtc,CurrentTime,out[i].x,out[i].y,out[i].mode,RR_Rotate_0,&out[i].id,1)!=RRSetConfigSuccess;
    }
    XSync(d,False);failed=failed||xerror;
    if(!failed) {
        XRRSetOutputPrimary(d,root,out[0].id);
        if(width!=groww || height!=growh)screen_size(width,height,oldw,oldh,mmw,mmh);
        XSync(d,False);failed=xerror;
    }
    if(failed) {
        /* Keep a failed modeset from leaving a previously working screen off. */
        XRRScreenResources *fresh=XRRGetScreenResourcesCurrent(d,root);
        if(fresh) {
            screen_size(groww,growh,oldw,oldh,mmw,mmh);
            for(int c=0;c<r->ncrtc;c++)XRRSetCrtcConfig(d,fresh,r->crtcs[c],CurrentTime,0,0,None,RR_Rotate_0,NULL,0);
            for(int c=0;c<r->ncrtc;c++) if(saved[c]->mode)
                XRRSetCrtcConfig(d,fresh,r->crtcs[c],CurrentTime,saved[c]->x,saved[c]->y,saved[c]->mode,saved[c]->rotation,saved[c]->outputs,saved[c]->noutput);
            XRRSetOutputPrimary(d,root,previous_primary);
            screen_size(oldw,oldh,oldw,oldh,mmw,mmh);XRRFreeScreenResources(fresh);
        }
    } else result=0;
    XUngrabServer(d);XSync(d,False);
    if(!failed) { usleep(30000);recover_windows(out,n,width,height); }
    for(int c=0;c<r->ncrtc;c++)XRRFreeCrtcInfo(saved[c]);
done:
    for(int i=0;i<n;i++)XRRFreeOutputInfo(out[i].info);
    XRRFreeScreenResources(r);
    if(result)fprintf(stderr,"ErdOS displays: layout could not be applied; retaining the previous configuration.\n");
    return result;
}
static uint64_t topology(void) {
    uint64_t h=1469598103934665603ULL;
    XRRScreenResources *r=XRRGetScreenResourcesCurrent(d,root);
    if(!r)return 0;
    for(int i=0;i<r->noutput;i++) {
        XRROutputInfo *o=XRRGetOutputInfo(d,r,r->outputs[i]);
        h=(h^r->outputs[i])*1099511628211ULL;
        if(o) {
            h=(h^((unsigned)o->connection | ((unsigned)non_desktop(r->outputs[i])<<8)))*1099511628211ULL;
            if(o->connection==RR_Connected)for(int k=0;k<o->nmode;k++)h=(h^o->modes[k])*1099511628211ULL;
            XRRFreeOutputInfo(o);
        }
    }
    XRRFreeScreenResources(r);return h;
}
int main(int argc,char **argv) {
    const char *arg=argc==2?argv[1]:"";
    if(strcmp(arg,"--apply") && strcmp(arg,"--watch") && strcmp(arg,"--watch-current") && strcmp(arg,"--stop")) {
        fprintf(stderr,"Usage: erdos-displays --apply|--watch|--watch-current|--stop\n");return 2;
    }
    d=XOpenDisplay(NULL);if(!d)return 1;XSetErrorHandler(on_error);root=DefaultRootWindow(d);
    Atom selection=XInternAtom(d,"_ERDOS_DISPLAY_WATCHER",False),stop=XInternAtom(d,"_ERDOS_DISPLAY_STOP",False);
    if(!strcmp(arg,"--stop")) {
        Window owner=XGetSelectionOwner(d,selection);
        if(owner) { XEvent e={0};e.xclient.type=ClientMessage;e.xclient.window=owner;e.xclient.message_type=stop;e.xclient.format=32;XSendEvent(d,owner,False,0,&e);XSync(d,False);
            for(int i=0;i<100 && XGetSelectionOwner(d,selection)==owner;i++)usleep(10000); }
        XCloseDisplay(d);return 0;
    }
    int event,error,major=1,minor=3;
    if(!XRRQueryExtension(d,&event,&error) || !XRRQueryVersion(d,&major,&minor) || major<1 || (major==1 && minor<3)) { XCloseDisplay(d);return 1; }
    if(!strcmp(arg,"--apply")) { int result=apply();XCloseDisplay(d);return result; }
    if(XGetSelectionOwner(d,selection)) { XCloseDisplay(d);return 0; }
    Window owner=XCreateSimpleWindow(d,root,0,0,1,1,0,0,0);
    XSetSelectionOwner(d,selection,owner,CurrentTime);
    unsigned long mask=RRScreenChangeNotifyMask|RROutputChangeNotifyMask|RROutputPropertyNotifyMask;
    if(major>1 || minor>=4)mask|=RRResourceChangeNotifyMask;
    XRRSelectInput(d,root,mask);
    if(!strcmp(arg,"--watch"))apply();
    uint64_t previous=topology();
    for(;;) {
        XEvent e;XNextEvent(d,&e);
        if(e.type==SelectionClear || (e.type==ClientMessage && e.xclient.message_type==stop))break;
        if(e.type==event+RRScreenChangeNotify)XRRUpdateConfiguration(&e);
        if(e.type!=event+RRScreenChangeNotify && e.type!=event+RRNotify)continue;
        usleep(200000); /* Debounce one hot-plug event burst; no periodic timer. */
        int stopping=0;
        while(XPending(d)) {
            XNextEvent(d,&e);
            if(e.type==SelectionClear || (e.type==ClientMessage && e.xclient.message_type==stop))stopping=1;
            if(e.type==event+RRScreenChangeNotify)XRRUpdateConfiguration(&e);
        }
        if(stopping)break;
        uint64_t current=topology();
        if(current!=previous) { apply();previous=topology(); }
    }
    XDestroyWindow(d,owner);XCloseDisplay(d);return 0;
}
