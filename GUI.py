#!/usr/bin/env python3
#Copyright Andrea Di Iorio 2020
#This file is part of FFmpegFastTrimConcat
#FFmpegFastTrimConcat is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.
#
#FFmpegFastTrimConcat is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.
#
#You should have received a copy of the GNU General Public License
#along with FFmpegFastTrimConcat.  If not, see <http://www.gnu.org/licenses/>.
#

from MultimediaManagementSys import *
from grouppingFunctions import sizeBatching
from utils import printList,TKINTER_COLORS
from configuration import *
from scriptGenerator import GenTrimReencodinglessScriptFFmpeg

import tkinter as tk
import tkinter.ttk as ttk
from tkinter import messagebox
from PIL import ImageTk, Image
from builtins import tuple
from functools import partial
from os import stat,environ as env
from copy import copy
from time import perf_counter,ctime
from sys import stderr,argv
from collections import namedtuple
from math import ceil

SelectedVids= dict() #SelTAG->vidItem
getTagColor=lambda tag,colors=TKINTER_COLORS: colors[hash(tag)%len(colors)]
#helper to (de)highlight a button
btnSel=lambda btn,colo="red": btn.config(highlightbackground=colo,highlightcolor=colo,\
  highlightthickness=BTN_SELECTED_THICKNESS,borderwidth=BTN_SELECTED_THICKNESS)
btnOff=lambda btn: btn.config(highlightbackground="black",highlightcolor="black",\
  highlightthickness=BTN_NN_SELECTED_THICKNESS,borderwidth=BTN_NN_SELECTED_THICKNESS)
##global vars supporting this GUI
RootTk=None
NextPGN =0  #next page => (subset) of items to grid
stopGifsUpdate=False #set to true when to stop the gifs update

###button logics
def _removeSelected(rmDict=SelectedVids):
    global SelectedVids,btns
    toRemove=unrollDictOfList(rmDict)
    if not messagebox.askyesno('REMOVE '+str(len(toRemove)),'Del?',icon='warning'): return
    for i in toRemove:
        if not remove(i): continue
        try:
            btn=btns[i.nameID]
            btnOff(btn)
            btn.config(state="disabled")
            del(i,btn,btns[i.nameID])
        except: pass

    rmDict.clear()
   
def _select(selected):
    """
        button pressed select an item
        operative mode determine if delete,play,add to SelectedVids...(global flags)
    """
    global SelectedVids,btns
    global PlayMode, SegSelectionMode, SegSelectionTimes,InfoAdd,\
             SelTAG,RemoveModeEnable, DeleteGroupKeepOne

    currentTotSelection=unrollDictOfList(SelectedVids)
    currentSelTag=SelTAG.get().strip()
    if currentSelTag not in SelectedVids: SelectedVids[currentSelTag]=list()

    button=btns[selected.nameID]
    print("\n:>>selected\t:",selected,"currentSelTag:",currentSelTag,\
        "currentTotSelection:",len(currentTotSelection))
    if CONF["DEBUG"]: print(SelectedVids)
    if PlayMode.get():
        target=selected.pathName
        if PLAY_SEGS_FIRST and len(selected.segPaths)>0: 
            target=" ".join(selected.segPaths)
            if selected.pathName!=None: target+=" "+selected.pathName#add also src
        return play(target)

    if RemoveModeEnable.get(): #remove the selection
        remTarget=[selected]
        if DeleteGroupKeepOne.get() and len(currentTotSelection)>1: 
            remTarget=currentTotSelection
            remTarget.append(selected)
            ## swap the largest selected element at the first position
            maxItemIdx,maxSize=0,remTarget[0].sizeB
            for i in range(len(remTarget)):
                if remTarget[i].sizeB>maxSize: maxItemIdx,maxSize=i,remTarget[i].sizeB
            #swap
            remTarget[0],remTarget[maxItemIdx]=remTarget[maxItemIdx],remTarget[0] 
            groupLeader=remTarget.pop(0)

        if messagebox.askyesno('REMOVE'+str(len(remTarget)), 'Remove?',icon='warning'):
            for t in remTarget:
                button=btns[t.nameID]
                if not remove(t): continue #not removed
                btnOff(button) #hide deletted item's btn
                button.config(state="disabled")
            del(button,btns[t.nameID],t)

        if DeleteGroupKeepOne.get(): SelectedVids.clear()
        return
    #not append to SelectedVids exec paths terminate here

    if len(selected.trimCmds)>0 and len(SegSelectionTimes.get().strip())==0:
        SegSelectionTimes.insert(0,selected.trimCmds[-1]) #add show trim cmd 
    
    newInfo=InfoAdd.get().strip()
    if newInfo!=DEFAULT_VID_INFOADD_STRING: 
        appendVidInfoStr(selected,newInfo)
        print("VID ADDITIONAL INFO:",selected.info[0])
    
    if SegSelectionMode.get() == 1:  #add cut points to the selected item
        #times = [float(x) for x in SegSelectionTimes.get().strip().split(" ") ] #ITERATIVE_TRIM_SEL CALL LOGIC
        #selected.cutPoints.extend([times])

        trimPoints=trimSegCommand(selected,SegSelectionTimes.get().strip(),newCmdOnErr=False)

        if len(trimPoints)>0:
            SelectedVids[currentSelTag].append(selected)
            print("cut commands:",selected.trimCmds,"cut points:",selected.cutPoints,sep="\n")
            button.flash()
            btnSel(button,"blue")
        else: pass #TODO MESSAGE BOX WARNING ERR TRIMMING
        return

    if selected in currentTotSelection: #rem already selected stuff
        for l in SelectedVids.values():
            if selected in l: l.remove(selected)
        print("Already selected so popped: ", selected)
        button.flash();button.flash()
        btnOff(button)
        return
    else: 
        SelectedVids[currentSelTag].append(selected)
        btnSel(button,getTagColor(currentSelTag))



def _flushSelectedItems(logFile=SELECTION_LOGFILE):
    global SelectedVids,btns
    selected=unrollDictOfList(SelectedVids)
    if len(selected)==0:    print(CRED,"nothing selected!!",CEND,file=stderr);return
    cumulSize,cumulDur= 0,0
    toTrim  =[i for i in selected if len(i.cutPoints)>0]
    
    cumulDur=sum([i.duration for i in selected])
    cumulSize=sum([i.sizeB   for i in selected])
    #write selected
    if logFile!=None:
        selectionLogFile=logFile+ctime().replace(" ", "_")
        if len(toTrim)>0:
            GenTrimReencodinglessScriptFFmpeg(toTrim,outFname=selectionLogFile)

        selectionInfos="\n# cumulSize: "+str(cumulSize / 2**20)+" MB "+"\t#cumulDur:"+str(cumulDur/60)+" min\n"
        f = open(selectionLogFile,"a")
        if len(toTrim)>0: f.write("\n\n\n##Selection not to trim")
        for tag,selList in SelectedVids.items():
            f.write(tag+"\n")
            f.writelines([i.pathName+"\n" for i in selList if len(i.cutPoints)==0])
        f.write(selectionInfos)
        f.close()
    print(selectionInfos)
    printList(selected)
    if len(toTrim)>0:
        print("trim script",GenTrimReencodinglessScriptFFmpeg(toTrim),sep="\n\n")

    #clear selected
    for i in selected:
        try:    #old page's button have been already destroied
            button=btns[i.nameID]
            btnOff(button) #hide deletted item's btn
        except:pass
    SelectedVids.clear()


class VerticalScrolledFrame(tk.Frame):
    """ 
        Tkinter vertical scrollable frame 
        Implemented with scrollB + (canvas->frame_interior) ->..widgects
        interior field to place widgets inside the scrollable frame
        Construct and pack/place/grid normally
    """

    def __init__(self, parent, *args, **kw):
        tk.Frame.__init__(self, parent, *args, **kw)

        # create a canvas object and a vertical scrollbar for scrolling it
        vscrollbar = tk.Scrollbar(self, orient=tk.VERTICAL,width=CONF["SCROLLBAR_W"],activebackground="green",bg="green")
        vscrollbar.pack(fill=tk.Y, side=tk.LEFT, expand=tk.FALSE)
        canvas = tk.Canvas(self, bd=0, highlightthickness=0, width=CANV_W,height=CANV_H, yscrollcommand=vscrollbar.set)
        # canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        vscrollbar.config(command=canvas.yview)
        vscrollbar.bind("<MouseWheel>", canvas.yview)
        # reset the view
        canvas.xview_moveto(0)
        canvas.yview_moveto(0)

        canvas.bind("<MouseWheel>", canvas.yview)
        # create a frame inside the canvas which will be scrolled with it
        self.interior = interior = tk.Frame(canvas)
        self.root=parent
        self.childs=list()  #object gridded inside the scrollable frame
        interior_id = canvas.create_window(0, 0, window=interior, anchor=tk.NW)

        # track changes to the canvas and frame width and sync them,
        # also updating the scrollbar
        def _configure_interior(event):
            # update the scrollbars to match the size of the inner frame
            ##frame filled W - H
            size = (interior.winfo_reqwidth(), interior.winfo_reqheight())
            canvas.config(scrollregion="0 0 %s %s" % size)  #TODO DEBUG -> HERE ALL ITEMS OF THE PAGE ?
            if interior.winfo_reqwidth() != canvas.winfo_width():
                # update the canvas's width to fit the inner frame
                canvas.config(width=interior.winfo_reqwidth())

        interior.bind('<Configure>', _configure_interior)

        def _configure_canvas(event):
            if interior.winfo_reqwidth() != canvas.winfo_width():
                # update the inner frame's width to fill the canvas
                canvas.itemconfigure(interior_id, width=canvas.winfo_width())

        canvas.bind('<Configure>', _configure_canvas)

PreviewTuple=namedtuple("PreviewTuple","showObj tumbnail gif")

####gif refresh functions
def getFrames(gifPath,max_frame_n=CONF["MAX_FRAME_N"]):
    frames = list()
    try:
        gif=Image.open(gifPath)
        for x in range(max_frame_n):
            frames.append(ImageTk.PhotoImage(gif.copy().convert("RGBA")))
            gif.seek(x+1)
    except EOFError: pass #reached EOF file
    except Exception as e:
           print(CRED,"getFrames",e,CEND,file=stderr)
    return frames
    

def update(gifs,root):
    global GifsUpdate
    if not GifsUpdate.get(): return;root.after(GIF_UPDATE_POLL*10,update,gifs,root)
    if CONF["AUDIT_PERF"]: start=perf_counter()
    for g in gifs:
        frameIdx=g.frameIdxRef[0]
        frame = g.frames[frameIdx]
        framesN=len(g.frames)
        g.frameIdxRef[0]=(frameIdx+1)%framesN
        g.showObj[0].configure(image=frame)
        
    if CONF["AUDIT_PERF"]: end=perf_counter();print("gifs reDrwaw in:",end-start)
    root.after(CONF["GIF_UPDATE_POLL"], update,gifs,root)

GifMetadTuple=namedtuple("GifMetadata","frames frameIdxRef showObj ")

def _restartGifsUpdate(root):
    global GifsUpdate,gifs
    if GifsUpdate.get(): root.after_idle(update,gifs,root)

####
def _getPreview(path,refObj,getGif=False):
    #fill a PreviewTuple with the img or gif if @getGif parsed at @path

    assert path!="","NULLPATH"
    
    if getGif:
        gif=GifMetadTuple(getFrames(path),[0],[refObj])
        if len(gif.frames) == 0:    return None
        return PreviewTuple(refObj,None,gif)
    
    try:                    
        img=Image.open(path)
    except Exception as e:  print("invalid prev at: ",path,"\t\t",e);return None
    return PreviewTuple(refObj,img,None)


def _drawPage(items, drawGif, root, decresePgN=False, pageNumber=None):
    #stub to draw a page of items,
    
    global NextPGN,sFrame,  nextPage
    lastPgN=ceil(len(items)/CONF["GUI_ITEMS_LIMIT"])-1 #starting from 0
    if pageNumber!=None: NextPGN=pageNumber
    if decresePgN: 
        NextPGN-=2  #-1 to return to already shown page, -1 to target prev pg
        if NextPGN<0: NextPGN=lastPgN

    #delete previous scroll frame
    #(global because this stub is linked to a btn -> would always pass the same ref)
    try:
        for c in sFrame.childs:
            c.destroy; del c
        sFrame.interior.destroy()
        sFrame.destroy()
        del sFrame
    except: pass
    #create a new context to draw items
    sFrame=VerticalScrolledFrame(root)
    sFrame.grid() #(row=1,column=0)
    
    print("drawing  page Num:", NextPGN,"on frame with id:", id(sFrame))
    assert NextPGN in range(0,lastPgN+1),"wrong pgN :("
    try:drawItems(items[NextPGN*CONF["GUI_ITEMS_LIMIT"]:(NextPGN+1)*CONF["GUI_ITEMS_LIMIT"]], drawGif, sFrame)
    except:pass
    NextPGN += 1
    if NextPGN*CONF["GUI_ITEMS_LIMIT"]>len(items): NextPGN = 0 #ring linked pages 
    nextPage.configure(text="nextPage: "+str(NextPGN)+"/"+str(lastPgN))


def drawItems(items,drawGif,mainFrame):
    """
        @items: items to draw, either as gifs to refresh or just tumbnails 
        @mainFrame: VerticalScrolledFrame root to put items elements
        @drawGif: draw and refresh periodically gifs in item.gifPath
                  otherwise use images at item.imgPath 
        @itemsToDrawLimit. also filtering of images to actually display possible
    """
    global btns, imgs,gifs
    gifs,imgs = list(),list()

    i,row, col,colSize=0,0,0,CONF["GUI_COLSIZE"]#aux indexes to progressivelly grid items
    
    start=perf_counter()

    try: del(btns)
    except: pass

    btns={ it.nameID:tk.Button(mainFrame.interior) for it in items }
    prevArgs=list() #preview path,target tkinter show object
    if drawGif:
        prevArgs=[ (items[i].gifPath,btns[items[i].nameID],True) for i in range(len(items))]
    else:   
        prevArgs=[ (items[i].imgPath,btns[items[i].nameID]) for i in range(len(items))]

    start=perf_counter()
    processed=list(map(lambda args: _getPreview(*args),prevArgs))  #serial, unpack args
    end=perf_counter()
    print("images parsing elapsed:",end-start)

    #fill buttons with preview parsed [concurrently]
    for p in range(len(processed)):
        prevTup=processed[p]
        if prevTup==None:   continue
        item=items[p]
        btn=prevTup.showObj
        img,gif=prevTup.tumbnail,prevTup.gif
        funcTmp = partial(_select, item)   #BIND FUNCTION FOR SELECTION

        backupCmds=""
        if len(item.trimCmds)> 0:  backupCmds=" backupCmds#="+str(len(item.trimCmds))

        txt = str(p)+": "
        if item.duration != 0:      txt += "duration:\t" + str(item.duration/60)[:6] +" mins"
        if item.sizeB != 0:         txt += "\nsize:\t" + str(item.sizeB/2**20)[:6]+"MB"
        if len(item.cutPoints)> 0:  #truncate cutpoints embedded in vid item
            cutStr=str(item.cutPoints).replace(" ","").replace("],"," ").replace(",","-").replace("[","").replace("]","").replace("'","")
            #txt += "\ncuts#="+str(len(item.cutPoints))
            #+truncString(": "+cutStr,14,suffixPatternToShowSep=None)
        if len(item.info[0])>0:    txt+="\n"+truncString(item.info[0],suffixPatternToShowSep=None)
        elif len(item.segPaths)> 0:  
            txt+="\nSegsReady#="+str(len(item.segPaths))
            if item.pathName == TMP_NOFULLVID: txt+="\n!NO FULL VIDEO!"
            else: txt+=backupCmds
        elif len(item.trimCmds)> 0:  txt+=backupCmds
        
        if drawGif:
            btn.configure(command=funcTmp,text=txt, \
                compound="center",fg="white", font=font)
            gifs.append(gif)
        else:
            try: tumbrl=ImageTk.PhotoImage(processed[i].tumbnail)
            except Exception as e: print("ImgParseErr:",e,item.imgPath,file=stderr);continue
            btn.configure(command=funcTmp,image=tumbrl, text=txt, \
                compound="center",fg="white", font=font)
            imgs.append(tumbrl) #avoid garbage collector to free the parsed imgs

        if CONF["DEBUG"]: print("Adding:",item.nameID,"showObj id:", id(btn), row, col, i)

        mainFrame.childs.append(btn)
        btn.grid(row=row, column=col)
        col += 1;i += 1
        if col >= colSize:
            col = 0
            row += 1
        for tag,selList in SelectedVids.items():
            if item in selList: btnSel(btn,getTagColor(tag))#color items prev.selected

    end=perf_counter()
    print("drawed: ",max(len(gifs),len(imgs)),"in secs: ",end-start)
    
    if drawGif :
        assert len(gifs)>0,"empty gif set -> nothing to show! items#"+str(len(items))
        mainFrame.interior.after_idle(update,gifs,mainFrame)


def _sortItems(items,sortMethod,drawGif,root,_evnt):
    vidItemsSorter(items,sortMethod.get())
    _drawPage(items,drawGif,root,pageNumber=0)

### GUI CORE
def itemsGridViewStart(itemsSrc,subWindow=False,drawGif=False,sort="size"):
    """
    start a grid view of the given items in the global tk root (new if None)
    @itemsSrc: items to show in the grid view
    @subWindow:draw gui elements in a subwindow 
        if root not exist, will be created as a standard empty window
    @drawGif: draw gif instead of img 
    @sort: items sorting, either: duration,size,sizeName,shuffle,nameID
    When tkinter root closed, Returns SelectedVids of items
    """
    global nextPage, items, RemoveModeEnable,SelectedVids
    global PlayMode, SegSelectionMode, SegSelectionTimes,InfoAdd,SelTAG, DeleteGroupKeepOne,GifsUpdate
    
    #get the gui tkinter container window for the element to grid inside
    root=None
    if subWindow:   root=tk.Toplevel()
    else:           root=tk.Tk()
    # root.resizable(True,True)

    items=None
    print("drawGif",drawGif)
    if drawGif:     items=FilterItems(itemsSrc,gifPresent=True,metadataPresent=True,durationPos=False)
    else:           items=FilterItems(itemsSrc,tumbnailPresent=True)
    for i in items:
        if i.sizeB == None:
            print(i)
    assert len(items)>0,"FILTERED ALL ITEMS"
    if CONF["DEBUG"]:       print("items to draw:");printList(items)
    #items=[i for i in itemsSrc if i!=None and i.pathName!=None and i.imgPath!=None]
    try: vidItemsSorter(items,sort)        #sort with the target method
    except Exception as e: print("sorting items fail with: ",e)
    
    
    ##global flags for the user, used in _select, when an item is selected 
    PlayMode= tk.BooleanVar()
    RemoveModeEnable=tk.BooleanVar(value=False)
    GifsUpdate=tk.BooleanVar(value=True)
    DeleteGroupKeepOne=tk.BooleanVar()
    SegSelectionMode = tk.IntVar()
    containerFrame = tk.Frame(root)
    containerFrame.grid(row=0,column=0)

    prevPg = partial(_drawPage,items,drawGif,root,True)
    prevPage = tk.Button(containerFrame, command=prevPg, text="<<prevPage",\
         background="yellow")
    prevPage.grid(row=0,column=0)
    nextPg = partial(_drawPage,items,drawGif,root)
    nextPage = tk.Button(containerFrame, command=lambda: _drawPage(items,drawGif,root), text="nextPage>>",\
         background="yellow")
    nextPage.grid(row=0, column=1)

    flushBtn = tk.Button(containerFrame, command=_flushSelectedItems,\
        text="printSelected", background="green")
    flushBtn.grid(row=0, column=2)  #flush items selected (print + file write)
    #sorting
    sortMethod=tk.StringVar(containerFrame,"size")
    sortItems=partial(_sortItems,items,sortMethod,drawGif,root)
    sortComboChoice=ttk.Combobox(containerFrame,textvar=sortMethod)
    sortComboChoice.bind("<<ComboboxSelected>>", sortItems)
    sortComboChoice["values"]=["duration","size","sizeName","nameID","segsReady&Size","shuffle"]
    sortComboChoice.grid(row=0,column=3)

    segSelectionEnable = tk.Checkbutton(containerFrame, text="segmentSelMode",\
        variable=SegSelectionMode) #TODO also flush->add: , command=_flushSelectedItems)
    segSelectionEnable.grid(row=2, column=0)

    SegSelectionTimes = tk.Entry(containerFrame,width=SEG_TRIM_ENTRY_WIDTH)
    SegSelectionTimes.insert(0, "start 10 20 ringrange 40 2 start 100 296 hole 155 175")
    SegSelectionTimes.grid(row=2, column=1)
    
    SelTAG= tk.Entry(containerFrame,width=3)
    SelTAG.insert(0, "DFLT_TAG")
    SelTAG.grid(row=3, column=0)
    
    InfoAdd= tk.Entry(containerFrame,width=len(DEFAULT_VID_INFOADD_STRING))
    InfoAdd.insert(0, DEFAULT_VID_INFOADD_STRING)
    InfoAdd.grid(row=2, column=2)
    

    __restartGifsUpdate=partial(_restartGifsUpdate,root)
    def radioTogglePlay_Gifs(): #exclusive gifsUpdate - playMode
        GifsUpdate.set(value=not PlayMode.get());__restartGifsUpdate()
        currentSelTag=SelTAG.get().strip()
        if PLAY_SELECTION_CUMULATIVE and PlayMode.get() and len(SelectedVids)>0:
            play(" ".join(unrollDictOfList(SelectedVids))) #play all selected

    playModeEnable= tk.Checkbutton(containerFrame, text="playMode",variable=PlayMode,\
        command=radioTogglePlay_Gifs,background="white")
    playModeEnable.grid(row=1, column=0)

    gifsUpdate=tk.Checkbutton(containerFrame, text="GifsUpdate",variable=GifsUpdate,command=__restartGifsUpdate)
    gifsUpdate.grid(row=1,column=1)
    #remove items UI logic
    remMode= tk.Checkbutton(containerFrame, text="removeMode",variable=RemoveModeEnable)
    remMode.grid(row=1,column=2)
    delGroup= tk.Checkbutton(containerFrame, text="DelGroupKeepOne",variable=DeleteGroupKeepOne)
    delGroup.grid(row=1,column=3)
    remSel=partial(_removeSelected,SelectedVids)
    delSelection=tk.Button(containerFrame,command=remSel, text="DEL_SELECTED",background="red")
    delSelection.grid(row=1, column=4)


    #root.after_idle(_nextPage,items,drawGif,sFrame)
    nextPg()
    if not subWindow: root.mainloop()

    return SelectedVids

def guiMinimalStartGroupsMode(groups,trgtAction=itemsGridViewStart,trgtActionExtraArgs=[],startSearch=".",sortOnGroupLen=True):
    """ @groups: dict of k-->itemsGroup to show on selection,
        @trgtAction: func to call on group select: items,[extraArgs] -> display
        @trgtActionExtraArgs: args to unpack & pass to @trgtAction after items

        When tkinter root closed, Returns SelectedVids of items
    """
    global nextPage,SelectedVids
    
    rootTk=tk.Tk()

    assert len(groups)>0,"empty groups given"
    ScrolledFrameGroup = VerticalScrolledFrame(rootTk)
    ScrolledFrameGroup.grid()

    groupItems = list(groups.items())
    if sortOnGroupLen:  groupItems.sort(key=lambda i: len(i[1]), reverse=True)
    else:               groupItems.sort(key=lambda i: i[0], reverse=True)#groupK

    for k, items in groupItems:
        #bind group select action
        gotoGroup = partial(trgtAction, items,*trgtActionExtraArgs) 

        cumulativeSize, cumulativeDur = 0, 0
        for item in items:
            cumulativeDur += int(item.duration)
            cumulativeSize += int(item.sizeB)
        #for each group key, display just a part if long key
        k=str(k)
        keyStr = k+" "
        if len(keyStr) > THRESHOLD_KEY_PRINT:
            keyStr = keyStr[:THRESHOLD_KEY_PRINT] + "... "
            widthIdx=k.lower().find("width") #if found show from resolution width
            if widthIdx >= 0: keyStr=k[widthIdx:widthIdx+THRESHOLD_KEY_PRINT]+"...."

        #selection button with related group info as label text
        groupBtnTxt = "groupK: " + keyStr + "\nnumElements: " + str(len(items))\
         + " size: "+str(cumulativeSize/2**20)+"MB dur: "+str(cumulativeDur/60)
        tk.Button(ScrolledFrameGroup.interior, text=groupBtnTxt,command=gotoGroup).grid()

    rootTk.mainloop()
    return SelectedVids

def argParseMinimal(args):
    # minimal arg parse use to parse optional args
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("pathStart", type=str, help="path to start recursive search of vids")
    parser.add_argument("--selectionMode", type=str, default="ITEMS",choices=["ITEMS","GROUPS"],\
                        help="ITEMS: select single items,\
                        GROUPS, select items in groups generated by --grouppingRule")

    parser.add_argument("--notReuseOldSerialization", type=str, default=False, \
                        help="not use items scanned previously in a namedTuple json serialization file")
    parser.add_argument("--itemsDumpFilepath", type=str, default=ITEMS_LAST_FOUND,\
                        help="use items scanned previously in a json serialization file\
                        \"\" to avoid or disable by env var set DUMP_ITEMS_FOUNDED=FALSE")
    parser.add_argument("--rescanAndMergeCutpoints",type=bool,default=False,\
                        help="update previous serialized items dump with a new scan,\
                        overwriting trimSegments fields in items with common nameID")
    parser.add_argument("--whitelistPaths",type=str,default=None,\
                        help="keep founded vid if match some nameID extracted from the given fpath list file")
    
    parser.add_argument("--grouppingRule", type=str,\
         default=ffmpegConcatDemuxerGroupping.__name__,choices=list(GrouppingFunctions.keys()),\
         help="groupping mode of items")

    nsArgParsed = parser.parse_args(args)
    nsArgParsed.grouppingRule = GrouppingFunctions[nsArgParsed.grouppingRule]   #set groupping function by selected name
    
    return nsArgParsed

if __name__ == "__main__": 
    args=argParseMinimal(argv[1:])
    grouppingFunc=ffmpegConcatDemuxerGroupping#ffmpegConcatFilterGroupping #
    items,itemsRestored=list(),list()
    ##Get items scanning fs or using previous backup
    start=perf_counter()
    reusePreviousSerialization=CONF["DUMP_ITEMS_FOUNDED"] and not args.notReuseOldSerialization
    previousDumpUsed=False
    if reusePreviousSerialization:
        try:#avoid fs scan reusing previous scanned items
            dumpFp=open(args.itemsDumpFilepath)
            print("stat of",dumpFp.name,stat(dumpFp.name))
            itemsRestored = deserializeSelection(dumpFp)
            print("restored:",len(itemsRestored))
            previousDumpUsed=True
        except:
            itemsRestored = list(ScanItems(args.pathStart, forceMetadataGen=False).values())
            args.itemsDumpFilepath=ITEMS_LAST_FOUND #force default serialization file

    if args.rescanAndMergeCutpoints or not reusePreviousSerialization:   #scan new vids[merge with serilization]
        items = list(ScanItems(args.pathStart, forceMetadataGen=False).values())
        if len(itemsRestored)>0: updateCutpointsFromSerialization(items, itemsRestored)
    else: items=itemsRestored

    if len(items) > 0: genMetadata(items)   #tuplelist are readOnly TODO REPLCE BY LIST INDEX, BUT DEL OBJ METHODS

    endItemsGet = perf_counter()
    print(len(items),"source items get in",endItemsGet-start,"used previous dump:",previousDumpUsed)

    #filtering
    items=FilterItems(items, metadataPresent=False,gifPresent=CONF["DRAW_GIF"], tumbnailPresent=(not CONF["DRAW_GIF"]),durationPos=False)
    if args.whitelistPaths!=None:
        itemsFull=items
        items=ItemsNamelistRestrict(items,args.whitelistPaths)

    for i in items: assert i.gifPath!=None
        
    ##selection mode
    if args.selectionMode=="GROUPS":
        groups=GetGroups(items,grouppingRule=grouppingFunc,startSearch=args.pathStart, \
                filterTumbnail=(not DRAW_GIF),filterGif=CONF["DRAW_GIF"])
        endGroupGet=perf_counter()
        print("source group get in",endGroupGet-endItemsGet,\
                "used previous dump ",args.itemsDumpFilepath)
        groups=FilterGroups(groups,100,mode="dur") #filter small groups
        guiMinimalStartGroupsMode(groups,trgtActionExtraArgs=[True,True])

    elif args.selectionMode=="ITEMS": itemsGridViewStart(items,drawGif=CONF["DRAW_GIF"])

    if CONF["DUMP_ITEMS_FOUNDED"]:# and args.whitelistPaths==None:
        if args.whitelistPaths!=None: items=itemsFull
        for x in range(len(items)):
            if isinstance(items[x],Vid): items[x]=items[x].toTuplelist()
        dump(items, open(args.itemsDumpFilepath,"w"), indent=JSON_INDENT)
        print("dumped on ",args.itemsDumpFilepath,len(items),"items")
        #if args.itemsDumpFilepath!="" and not args.rescanAndMergeCutpoints:        else: SerializeSelection(items,filename=ITEMS_LAST_FOUND)
