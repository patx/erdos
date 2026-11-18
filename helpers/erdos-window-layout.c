/* SPDX-License-Identifier: MIT
 * Small X11 window tiler. Restore geometry lives on each window, not on disk.
 * Compiled on Debian 13; uses X11/RandR libraries already present in the image.
 */
#include <X11/Xlib.h>
#include <X11/Xatom.h>
#include <X11/extensions/Xrandr.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

typedef struct { int x, y, w, h; } Rect;
static Display *d;
static Window root;
static Atom atom(const char *s) { return XInternAtom(d, s, False); }
static int ignore_error(Display *display, XErrorEvent *event) {
    (void)display; (void)event; return 0;
}
static unsigned long *property(Window w, const char *name, unsigned long *n) {
    Atom type; int format; unsigned long rest; unsigned char *data = NULL;
    *n = 0;
    if (XGetWindowProperty(d, w, atom(name), 0, 4096, False, AnyPropertyType,
                          &type, &format, n, &rest, &data) != Success || format != 32) {
        if (data) XFree(data);
        *n = 0; return NULL;
    }
    return (unsigned long *)data;
}
static int state(Window w, const char *name) {
    unsigned long n, *p = property(w, "_NET_WM_STATE", &n); int found = 0;
    for (unsigned long i = 0; i < n; ++i) if (p[i] == atom(name)) found = 1;
    if (p) XFree(p);
    return found;
}
static void send(Window w, const char *name, long a, long b, long c, long e, long f) {
    XEvent event = {0}; event.xclient.type = ClientMessage;
    event.xclient.window = w; event.xclient.message_type = atom(name);
    event.xclient.format = 32; event.xclient.data.l[0] = a;
    event.xclient.data.l[1] = b; event.xclient.data.l[2] = c;
    event.xclient.data.l[3] = e; event.xclient.data.l[4] = f;
    XSendEvent(d, root, False, SubstructureRedirectMask | SubstructureNotifyMask, &event);
    XFlush(d);
}
static int unmaximize(Window w) {
    send(w, "_NET_WM_STATE", 0, atom("_NET_WM_STATE_MAXIMIZED_VERT"),
         atom("_NET_WM_STATE_MAXIMIZED_HORZ"), 2, 0);
    for (int i = 0; i < 100; ++i) {
        if (!state(w, "_NET_WM_STATE_MAXIMIZED_VERT") &&
            !state(w, "_NET_WM_STATE_MAXIMIZED_HORZ")) return 1;
        usleep(10000);
    }
    return 0;
}
static Rect geometry(Window w) {
    XWindowAttributes a; Window child; Rect r = {0};
    if (!XGetWindowAttributes(d, w, &a)) return r;
    XTranslateCoordinates(d, w, root, 0, 0, &r.x, &r.y, &child);
    r.w = a.width; r.h = a.height; return r;
}
static long overlap(Rect a, Rect b) {
    int l = a.x > b.x ? a.x : b.x, t = a.y > b.y ? a.y : b.y;
    int r = a.x+a.w < b.x+b.w ? a.x+a.w : b.x+b.w;
    int bot = a.y+a.h < b.y+b.h ? a.y+a.h : b.y+b.h;
    return r > l && bot > t ? (long)(r-l)*(bot-t) : 0;
}
static Rect workarea(Rect window) {
    Rect monitor = {0, 0, DisplayWidth(d, DefaultScreen(d)), DisplayHeight(d, DefaultScreen(d))};
    int count = 0; long best = -1;
    XRRMonitorInfo *monitors = XRRGetMonitors(d, root, True, &count);
    for (int i = 0; monitors && i < count; ++i) {
        Rect candidate = {monitors[i].x, monitors[i].y, monitors[i].width, monitors[i].height};
        long area = overlap(window, candidate);
        if (area > best) { best = area; monitor = candidate; }
    }
    if (monitors) XRRFreeMonitors(monitors);
    unsigned long n, desk = 0, *p = property(root, "_NET_CURRENT_DESKTOP", &n);
    if (n) desk = p[0];
    if (p) XFree(p);
    /* Apply panel struts only to monitors they actually touch. A global work
     * area would incorrectly reserve the laptop's top bar on external screens. */
    unsigned long clients_n, *clients=property(root,"_NET_CLIENT_LIST",&clients_n);
    Rect usable=monitor;int right=monitor.x+monitor.w,bottom=monitor.y+monitor.h,found=0;
    int rootw=DisplayWidth(d,DefaultScreen(d)),rooth=DisplayHeight(d,DefaultScreen(d));
    for(unsigned long i=0;i<clients_n;i++) {
        unsigned long count,*desktop=property(clients[i],"_NET_WM_DESKTOP",&count);
        unsigned long desktop_id=count ? (desktop[0]&0xffffffffUL):0;
        int visible=!count || desktop_id==desk || desktop_id==0xffffffffUL;
        if(desktop)XFree(desktop);
        if(!visible)continue;
        unsigned long *v=property(clients[i],"_NET_WM_STRUT_PARTIAL",&count);
        if(count<4) { if(v)XFree(v);v=property(clients[i],"_NET_WM_STRUT",&count); }
        if(count>=4) {
            found=1;
            int left=v[0]>(unsigned)rootw?rootw:(int)v[0];
            int r=v[1]>(unsigned)rootw?rootw:(int)v[1];
            int top=v[2]>(unsigned)rooth?rooth:(int)v[2];
            int b=v[3]>(unsigned)rooth?rooth:(int)v[3];
            int vertical_left=count>=12 ? (int)v[4]:0,vertical_left_end=count>=12?(int)v[5]:rooth-1;
            int vertical_right=count>=12?(int)v[6]:0,vertical_right_end=count>=12?(int)v[7]:rooth-1;
            int horizontal_top=count>=12?(int)v[8]:0,horizontal_top_end=count>=12?(int)v[9]:rootw-1;
            int horizontal_bottom=count>=12?(int)v[10]:0,horizontal_bottom_end=count>=12?(int)v[11]:rootw-1;
            if(left && vertical_left<bottom && vertical_left_end>=monitor.y && left>usable.x)usable.x=left;
            if(r && vertical_right<bottom && vertical_right_end>=monitor.y && rootw-r<right)right=rootw-r;
            if(top && horizontal_top<monitor.x+monitor.w && horizontal_top_end>=monitor.x && top>usable.y)usable.y=top;
            if(b && horizontal_bottom<monitor.x+monitor.w && horizontal_bottom_end>=monitor.x && rooth-b<bottom)bottom=rooth-b;
        }
        if(v)XFree(v);
    }
    if(clients)XFree(clients);
    if(found && right>usable.x && bottom>usable.y) {
        usable.w=right-usable.x;usable.h=bottom-usable.y;return usable;
    }
    p = property(root, "_NET_WORKAREA", &n);
    if (desk < n/4) {
        Rect available = {(int)p[4*desk], (int)p[4*desk+1], (int)p[4*desk+2], (int)p[4*desk+3]};
        int right = monitor.x+monitor.w, bottom = monitor.y+monitor.h;
        if (available.x > monitor.x) monitor.x = available.x;
        if (available.y > monitor.y) monitor.y = available.y;
        if (available.x+available.w < right) right = available.x+available.w;
        if (available.y+available.h < bottom) bottom = available.y+available.h;
        if (right > monitor.x && bottom > monitor.y) {
            monitor.w = right-monitor.x; monitor.h = bottom-monitor.y;
        }
    }
    if (p) XFree(p);
    return monitor;
}
static void move(Window w, Rect r) {
    /* Openbox's NorthWestGravity anchors the frame. StaticGravity also adds
     * the client's original border, which Xorg hides after reparenting. */
    unsigned long n, *ext = property(w, "_NET_FRAME_EXTENTS", &n);
    if (n == 4) { r.x -= (int)ext[0]; r.y -= (int)ext[2]; }
    if (ext) XFree(ext);
    send(w, "_NET_MOVERESIZE_WINDOW", NorthWestGravity | (15<<8) | (2<<12), r.x, r.y, r.w, r.h);
}
int main(int argc, char **argv) {
    const char *mode = argc == 2 ? argv[1] : "";
    const char *valid[] = {"left","right","top","bottom","top-left","top-right","bottom-left","bottom-right","maximize","restore"};
    int known = 0;
    for (unsigned i=0; i<sizeof(valid)/sizeof(valid[0]); ++i) if (!strcmp(mode, valid[i])) known=1;
    if (!known) { fprintf(stderr,"Usage: erdos-window-layout left|right|top|bottom|top-left|top-right|bottom-left|bottom-right|maximize|restore\n"); return 2; }
    d = XOpenDisplay(NULL); if (!d) return 1;
    XSetErrorHandler(ignore_error); root = DefaultRootWindow(d);
    unsigned long n, *p = property(root, "_NET_ACTIVE_WINDOW", &n);
    Window w = n ? p[0] : None; if (p) XFree(p);
    if (!w || w == root || state(w, "_NET_WM_STATE_FULLSCREEN")) { XCloseDisplay(d); return 0; }
    if (!unmaximize(w)) { XCloseDisplay(d); return 1; }
    Rect original = geometry(w);
    if (original.w <= 0 || original.h <= 0) { XCloseDisplay(d); return 0; }
    p = property(w, "_ERDOS_RESTORE_GEOMETRY", &n);
    if (!strcmp(mode, "restore")) {
        if (n == 4) {
            Rect saved = {(int)p[0],(int)p[1],(int)p[2],(int)p[3]};
            if (saved.w > 0 && saved.h > 0) {
                /* A monitor may have been removed since this rectangle was saved. */
                int rw=DisplayWidth(d,DefaultScreen(d)),rh=DisplayHeight(d,DefaultScreen(d));
                if(saved.x<0 || saved.y<0 || saved.x+saved.w>rw || saved.y+saved.h>rh) {
                    Rect area=workarea(saved);unsigned long en,*ext=property(w,"_NET_FRAME_EXTENTS",&en);
                    int left=en==4?(int)ext[0]:0,right=en==4?(int)ext[1]:0;
                    int top=en==4?(int)ext[2]:0,bottom=en==4?(int)ext[3]:0;
                    if(ext)XFree(ext);
                    int minx=area.x+left,miny=area.y+top;
                    int maxx=area.x+area.w-right-saved.w,maxy=area.y+area.h-bottom-saved.h;
                    if(maxx<minx)maxx=minx;
                    if(maxy<miny)maxy=miny;
                    if(saved.x<minx)saved.x=minx;
                    if(saved.x>maxx)saved.x=maxx;
                    if(saved.y<miny)saved.y=miny;
                    if(saved.y>maxy)saved.y=maxy;
                }
                move(w,saved);
            }
            XDeleteProperty(d, w, atom("_ERDOS_RESTORE_GEOMETRY"));
        }
    } else {
        if (n != 4) {
            unsigned long saved[4] = {(unsigned long)original.x,(unsigned long)original.y,
                                      (unsigned long)original.w,(unsigned long)original.h};
            XChangeProperty(d,w,atom("_ERDOS_RESTORE_GEOMETRY"),XA_CARDINAL,32,PropModeReplace,(unsigned char *)saved,4);
        }
        if (!strcmp(mode,"maximize")) {
            send(w,"_NET_WM_STATE",1,atom("_NET_WM_STATE_MAXIMIZED_VERT"),atom("_NET_WM_STATE_MAXIMIZED_HORZ"),2,0);
        } else {
            Rect area=workarea(original), target=area;
            if (strcmp(mode,"top") && strcmp(mode,"bottom")) target.w=area.w/2;
            if (strcmp(mode,"left") && strcmp(mode,"right")) target.h=area.h/2;
            if (strstr(mode,"right")) target.x=area.x+area.w-target.w;
            if (strstr(mode,"bottom")) target.y=area.y+area.h-target.h;
            unsigned long extn, *ext=property(w,"_NET_FRAME_EXTENTS",&extn);
            if (extn==4) { target.x+=(int)ext[0]; target.y+=(int)ext[2]; target.w-=(int)(ext[0]+ext[1]); target.h-=(int)(ext[2]+ext[3]); }
            if (ext) XFree(ext);
            if (target.w>0 && target.h>0) move(w,target);
        }
    }
    if (p) XFree(p);
    XSync(d,False); XCloseDisplay(d); return 0;
}
