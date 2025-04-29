import sys, os, string, math, re, random, numpy, copy
import json, time
from datetime import datetime
import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.markers import MarkerStyle

user = os.getlogin()
sys.path.append('C:/Users/%s/Dropbox/Instruments cloud/Robotics/Unchained BK/AS Scripts/API Scripts' % user)


class CustomScheduler:
    
    def __init__(self, log):
        self.timelog = os.path.basename(log)
        self.dir = os.path.dirname(log)
        self.log = None
         

    def date_log(self,s,t0):
         d = datetime.strptime(s,"%m-%d-%Y %H:%M:%S")
         t=int(d.timestamp())
         if t0==0:
             t0=t
         tabs=float(t-t0)/60
         return t0, tabs


    def read_logbook(self,NS_min,kinds):
         plt.ioff() 
         cmap = plt.get_cmap('rainbow')
     
         try:
            self.log=pd.read_csv(os.path.join(d,self.timelog),
                          skip_blank_lines=True,
                          comment=";")
         except:
            return 0,None,None,None

         t=[] #absolute end times
         n=0
         chunk=0
         t0=0
         last={}
         m=len(kinds)

         for i,u in self.log.iterrows():
                    ns=self.log['NS'][i]
                    duration=self.log['time(min)'][i]
                    chunk+=duration/ns
                    ex=self.log['expno'][i]                
                    name=self.log['name'][i]  
                    t0, tabs = self.date_log(self.log['started'][i],t0)
                    t.append(tabs+duration )
                    k = "%s_%d" % (name,ex)
                    last[k]=i
                    j=kinds.index(k)
                    c=cmap(0.99*j/(m-1))
                    plt.scatter(tabs/60,0,s=50,color=c,
                                marker=MarkerStyle('o',fillstyle='full'))
                    plt.scatter(tabs/60,j+1,s=50,color=c,
                                marker=MarkerStyle('o',fillstyle='full'))
                    n+=1
     
         chunk*=NS_min/n   
         offsets=[]
     
         for k in kinds:
                 lag=-int(0.5+(t[-1]-t[last[k]])/chunk) 
                 offsets.append(lag)
     
         for j in range(m):
             plt.axhline(y=j+1, color=cmap(0.99*j/(m-1)))  
         
         plt.xlabel("start time, h")
         plt.minorticks_on()
         plt.yticks([])
         #plt.show() 
         plt.savefig(os.path.join(d,"F80_history.jpg"))
         plt.close()
         plt.ion()      
         
         return chunk,offsets,last,self.log
 
    
    def do_schedule(self,q,periods_,offsets_):
         periods=np.array(periods_)
         offsets=np.array(offsets_)
         index=np.argsort(periods)
         n=len(periods)
         tmax=q*np.max(periods)
    
         tm_=[]
         col_=[]
         m=0
         for j0 in range(n):
             j=index[j0]
             t=offsets[j]
             while  t<=tmax:
                 if(t>=0):
                     tm_.append(t)
                     col_.append((j,j0))
                     m+=1          
                 t+=periods[j]
     
         tm=np.array(tm_,dtype='f')
         col=np.array(col_)
         tm,col = sort2(tm,col)
     
         q=0
         v=[]
         for i in range(m):
             if tm[i]>q or i==m-1:
                d=tm[i]-q
                if len(v)>1:
                    for u in v:
                        tm[u]+=d*col[u][1]/n
                v=[]
                q=tm[i]
             v.append(i)
             j+=1
     
         planner=[]
         for i in range(m):
             planner.append((col[i][0],tm[i]))
     
         return planner 

    def plot_schedule(self,d,planner,offsets):
        plt.ioff()
        n=len(offsets)
        cmap = plt.get_cmap('rainbow')
    
        for i in range(n):
            c=cmap(0.99*i/(n-1))
            plt.scatter(offsets[i],0,s=50,color=c,
                        marker=MarkerStyle('o',fillstyle='none'),linewidth=3)
            plt.scatter(offsets[i],i+1,s=100,color=c,
                        marker=MarkerStyle('o',fillstyle='none'),linewidth=3)
            plt.axhline(y=i+1, color=c)
        
        for p in planner:
            c=cmap(0.99*p[0]/(n-1))
            plt.scatter(p[1],0,s=50,color=c,
                        marker=MarkerStyle('o',fillstyle='full'))
            plt.scatter(p[1],p[0]+1,s=100,color=c,
                        marker=MarkerStyle('o',fillstyle='full'))
        plt.xlabel("time, chunks")
        plt.axvline(x=0, color='k', linestyle='dashed')
        plt.minorticks_on()
        plt.yticks([])
        #plt.show() 
        plt.savefig(self.timelog)
        plt.close()
        plt.ion()

   
