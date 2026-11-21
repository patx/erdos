/* SPDX-License-Identifier: MIT
 * Set libinput properties through the X server; no root or input-device access. */
#include <X11/Xlib.h>
#include <X11/extensions/XInput2.h>
#include <X11/extensions/XInput.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static int failed;
static int error(Display *d, XErrorEvent *e) {(void)d;(void)e;failed=1;return 0;}
static int property(Display *d,int id,const char *name,Atom type,int format,void *value,int count) {
    Atom p=XInternAtom(d,name,True),actual;int bits;unsigned long n,left;unsigned char *data=NULL;
    if(p==None)return 0;
    XIGetProperty(d,id,p,0,16,False,AnyPropertyType,&actual,&bits,&n,&left,&data);
    if(data)XFree(data);
    if(actual!=type || bits!=format || n!=(unsigned)count)return 0;
    XIChangeProperty(d,id,p,type,format,PropModeReplace,value,count);return 1;
}
int main(int argc,char **argv) {
    if(argc!=6)return 2;
    if(strcmp(argv[5],"0") && strcmp(argv[5],"1"))return 2;
    for(int i=1;i<4;i++)if(strcmp(argv[i],"0") && strcmp(argv[i],"1"))return 2;
    char *end;float speed=strtof(argv[4],&end);
    if(*end || !(speed>=-1 && speed<=1))return 2;
    Display *d=XOpenDisplay(NULL);if(!d)return 1;XSetErrorHandler(error);
    int n=0,found=0;XIDeviceInfo *devices=XIQueryDevice(d,XIAllDevices,&n);
    Atom integer=XInternAtom(d,"INTEGER",False),floating=XInternAtom(d,"FLOAT",False);
    for(int i=0;i<n;i++) {
        if(devices[i].use!=XISlavePointer)continue;
        unsigned char tap=atoi(argv[2]);
        /* Tapping is a touchpad-only property; leave mice untouched. */
        if(!property(d,devices[i].deviceid,"libinput Tapping Enabled",integer,8,&tap,1))continue;
        found++;
        /* Map touchpad middle-click to an otherwise unused Openbox button.
         * Mice retain their middle button. Disabling reverses our mapping. */
        XDevice *device=XOpenDevice(d,devices[i].deviceid);
        if(device) {
            unsigned char map[256];
            int count=XGetDeviceButtonMapping(d,device,map,256);
            int enabled=atoi(argv[5]);
            if(count>=2 && ((enabled && map[1]==2) || (!enabled && map[1]==10))) {
                for(int j=0;j<count;j++) {
                    if(map[j]==2)map[j]=10;
                    else if(map[j]==10)map[j]=2;
                }
                if(XSetDeviceButtonMapping(d,device,map,count)!=MappingSuccess)failed=1;
            }
            XCloseDevice(d,device);
        } else failed=1;
        unsigned char natural=atoi(argv[1]),click[2]={!atoi(argv[3]),atoi(argv[3])};
        property(d,devices[i].deviceid,"libinput Natural Scrolling Enabled",integer,8,&natural,1);
        property(d,devices[i].deviceid,"libinput Click Method Enabled",integer,8,click,2);
        property(d,devices[i].deviceid,"libinput Accel Speed",floating,32,&speed,1);
    }
    if(devices)XIFreeDeviceInfo(devices);
    XSync(d,False);XCloseDisplay(d);
    if(!found){fprintf(stderr,"No compatible touchpad connected. Preferences will apply at next login.\n");return 3;}
    if(failed){fprintf(stderr,"The touchpad rejected one or more settings.\n");return 1;}
    return 0;
}
