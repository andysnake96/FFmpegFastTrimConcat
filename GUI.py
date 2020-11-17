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
from builtins import tuple
from turtledemo.forest import start

from MultimediaManagementSys import *
from grouppingFunctions import sizeBatching
from utils import printList
from configuration import MAX_FRAME_N,BAR_W

import tkinter as tk
from tkinter import messagebox
from PIL import ImageTk, Image
from functools import partial
from os import environ as env
from copy import copy
from time import perf_counter,ctime
from sys import stderr,argv
from collections import namedtuple

SelectedList = list()       #selection modified by GUI 
#helper to (de)highlight a button
btnSel=lambda btn: btn.config(highlightbackground="red",highlightcolor= "red",\
  highlightthickness=BTN_SELECTED_THICKNESS,borderwidth=BTN_SELECTED_THICKNESS)
btnOff=lambda btn: btn.config(highlightbackground="black",highlightcolor="black",\
  highlightthickness=BTN_NN_SELECTED_THICKNESS,borderwidth=BTN_NN_SELECTED_THICKNESS)
##global vars supporting this GUI
RootTk=None
pgN =0  #page (subset) of items to grid
stopGifsUpdate=False #set to true when to stop the gifs update

###button logics
def _removeSelected(remTarget=SelectedList):
    global SelectedList,btns
    if not messagebox.askyesno('REMOVE ALL '+str(len(remTarget)),'Del?',icon='warning'):
        return
    for i in remTarget:
        btn=btns[i.nameID]
        if not remove(i): continue #not removed
        btnOff(btn)
        btn.config(state="disabled")
        del(i,btn,btns[i.nameID])

    SelectedList=list()
    
def _select(selected):
    """
        button pressed select an item
        operative mode determine if delete,play,append to SelectedList...(global flags)
    """
    global SelectedList,btns
    #operative mode selection modifiers
    global PlayMode, SegSelectionMode, SegSelectionTimes, RemoveModeEnable, DeleteGroupKeepOne

    button=btns[selected.nameID]
    print("selected\t:",selected,"current tot selection:",len(SelectedList))

    if PlayMode.get(): return selected.play()

    if RemoveModeEnable.get(): #remove the selection
        remTarget=[selected]
        if DeleteGroupKeepOne.get() and len(SelectedList)>1: 
            remTarget=SelectedList
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

        if DeleteGroupKeepOne.get(): SelectedList=list()
        return

    if SegSelectionMode.get() == 1:  #add cut points to the selected item
        times = [float(x) for x in SegSelectionTimes.get().strip().split(" ") ] #ITERATIVE_TRIM_SEL CALL LOGIC
        selected.cutPoints.extend([times]) #TODO EXTRACT/ENHANCE MMSYS ITERATIVE CUT AND PARSE HERE Entry's string
        SelectedList.append(selected)
        button.flash()
        return

    if selected in SelectedList and len(selected.cutPoints)==0:#already selected in normalmode
        SelectedList.remove(selected)
        print("Already selected so popped: ", selected)
        button.flash();button.flash()
        btnOff(button)
        return
    else: 
        SelectedList.append(selected)
        btnSel(button)
    #highlight selected button


def buildFFmpegCuts(item,seekOutputOpt=False):
    outStr=""
    encode_out="-c:v copy -avoid_negative_ts make_zero -n out.mp4"
    for points in item.cutPoints:
        cutCmd= "ffmpeg "+" -ss "+str(points[0])+" -to "+str(points[1])+" -i "+item.pathName+encode_out
        if seekOutputOpt:
            cutCmd= "ffmpeg -i "+item.pathName+ "-ss "+str(points[0])+" -to "+str(points[1])+encode_out
        outStr+=cutCmd
    return outStr


def _flushSelectedItems(selected=SelectedList):
    global SelectedList,btns

    if len(selected)==0:    return
    cumulSize,cumulDur= 0,0
    lines = list()
    for i in selected:
        #print(i.pathName, "\t\t ", int(i.sizeB) / 2 ** 20, " MB")
        if i.cutPoints!=[]: lines.append(buildFFmpegCuts(i)) #ffmpeg cut standard
        else:               lines.append(i.pathName+"\n")
        
        cumulSize+= int(i.sizeB)
        cumulDur+= int(i.duration)

    if SELECTION_LOGFILE != "":
        f = open(SELECTION_LOGFILE + ctime().replace(" ", "_")+".list" , "w")
        selectionInfos="# cumulSize: "+str(cumulSize / 2**20)+" MB\n"+"\t cumulDur:"+str(cumulDur/60)+" min\n"
        f.write(selectionInfos)
        f.writelines(lines)
        f.close()
    #clear selection
    for i in SelectedList:
        try:    #old page's button have been already destroied
            button=btns[i.nameID]
            btnOff(button) #hide deletted item's btn
        except:pass
    SelectedList.clear()

    print(selectionInfos)
    printList(lines)

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
        vscrollbar = tk.Scrollbar(self, orient=tk.VERTICAL,width=BAR_W,activebackground="green",bg="green")
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
def getFrames(gifPath,max_frame_n=MAX_FRAME_N):
    frames = list()
    try:
        gif=Image.open(gifPath)
        for x in range(max_frame_n):
            frames.append(ImageTk.PhotoImage(gif.copy().convert("RGBA")))
            gif.seek(x+1)
    except EOFError: pass #reached EOF file
    except Exception as e:
           print("getFrames",e,file=stderr)
    return frames
    

def update(gifs,root):
    global stopGifsUpdate 
    if stopGifsUpdate: return   #TODO SUB WINDOW CLOSE EVENT -> SET THIS FLAG!!!

    for g in gifs:
        frameIdx=g.frameIdxRef[0]
        frame = g.frames[frameIdx]
        framesN=len(g.frames)
        g.frameIdxRef[0]=(frameIdx+1)%framesN
        g.showObj[0].configure(image=frame)
        
        if DEBUG:   print("showObj id:",id(g.showObj[0]))
    root.after(GIF_UPDATE_POLL, update,gifs,root)

GifMetadTuple=namedtuple("GifMetadata","frames frameIdxRef showObj ")

####
def _getPreview(path,refObj,getGif=False):
    #fill a PreviewTuple with the img or gif if @getGif parsed at @path

    assert path!="","NULLPATH"
    
    if getGif!=None:
        gif=GifMetadTuple(getFrames(path),[0],[refObj])
        if len(gif.frames) == 0:    return None
        return PreviewTuple(refObj,None,gif)
    
    try:                    
        img=Image.open(path) #img=ImageTk.PhotoImage(Image.open(imgPath))  

    except Exception as e:  print("invalid prev at: ",path,"\t\t",e)
    return PreviewTuple(refObj,img,None)


def _nextPage(items,drawGif,root):
    #stub to draw a page of items with global var pgN 
    global pgN,sFrame
    if pgN*GUI_ITEMS_LIMIT > len(items): pgN = 0  # circular next page

    #delete previous scroll frame
    #(global because this stub is linked to a btn -> woud always pass the same ref)
    try:
        for c in sFrame.childs:
            c.destroy; del c
        sFrame.interior.destroy()
        sFrame.destroy()
        del sFrame
    except: pass

    sFrame=VerticalScrolledFrame(root)
    sFrame.grid() #(row=1,column=0)

    drawItems(items[pgN*GUI_ITEMS_LIMIT:(pgN+1)*GUI_ITEMS_LIMIT],drawGif,sFrame)

    pgN += 1
    print("nextpgNumber :", pgN,id(sFrame))
    #nextPage.configure(text="nextPage: "+str(pgN))


def drawItems(items,drawGif,mainFrame):
    """
        @items: items to draw, either as gifs to refresh or just tumbnails 
        @mainFrame: VerticalScrolledFrame root to put items elements
        @drawGif: draw and refresh periodically gifs in item.gifPath
                  otherwise use images at item.imgPath 
        @itemsToDrawLimit. also filtering of images to actually display possible
    """
    global btns, imgs
    gifs,imgs = list(),list()

    i,row, col,colSize=0,0,0,GUI_COLSIZE #aux indexes to progressivelly grid items
    
    start=perf_counter()

    try: del(btns)
    except: pass

    btns={ it.nameID:tk.Button(mainFrame.interior) for it in items }
    prevArgs=list() #preview path,target tkinter show object
    if drawGif:
        prevArgs=[ (items[i].gifPath,btns[items[i].nameID]) for i in range(len(items))]
    else:   
        prevArgs=[ (items[i].imgPath,btns[items[i].nameID]) for i in range(len(items))]

    start=perf_counter()
    if len(prevArgs)>POOL_TRESHOLD and not drawGif: #multi process image parsing
          print("worker pool concurrent image parsing")
          processed=list(concurrentPoolProcess(prevArgs,_getPreview,"badTumbNail",POOL_SIZE))
    else: processed=list(map(lambda args: _getPreview(*args),prevArgs))  #serial, unpack args
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

        txt = str(p)+": "
        if item.duration != 0: txt += "len secs\t" + str(item.duration)
        if item.sizeB != 0:    txt += "\nsize bytes\t" + str(item.sizeB)
        
        if drawGif:
            btn.configure(command=funcTmp,text=txt, \
                compound="center",fg="white", font=font)
            gifs.append(gif)
        else:
            try: tumbrl=ImageTk.PhotoImage(processed[i])
            except Exception as e: print("ImgParseErr:",e,item.imgPath,file=stderr);continue
            btn.configure(command=funcTmp,image=tumbrl, text=txt, \
                compound="center",fg="white", font=font)
            imgs.append(tumbrl) #avoid garbage collector to free the parsed imgs

        if DEBUG: print("Adding:",item.nameID,"showObj id:", id(btn), row, col, i)

        mainFrame.childs.append(btn)
        btn.grid(row=row, column=col)
        col += 1;i += 1
        if col >= colSize:
            col = 0
            row += 1

    end=perf_counter()
    print("drawed: ",max(len(gifs),len(imgs)),"in secs: ",end-start)
    
    if drawGif :
        assert len(gifs)>0,"empty gif set -> nothing to show!"
        mainFrame.interior.after_idle(update,gifs,mainFrame)




### GUI CORE
def itemsGridViewStart(itemsSrc,subWindow=False,drawGif=False,sort="size"):
    """
    start a grid view of the given items in the global tk root (new if None)
    @itemsSrc: items to show in the grid view
    @subWindow:draw gui elements in a subwindow 
        if root not exist, will be created as a standard empty window
    @drawGif: draw gif instead of img 
    @sort: items sorting, either: duration,size,sizeName,shuffle,nameID
    When tkinter root closed, Returns SelectedList of items
    """
    global nextPage, items, RemoveModeEnable
    global PlayMode, SegSelectionMode, SegSelectionTimes, DeleteGroupKeepOne
    
    #get the gui tkinter container window for the element to grid inside
    root=None
    if subWindow:   root=tk.Toplevel()
    else:           root=tk.Tk()
    # root.resizable(True,True)

    items=None
    if drawGif:     items=FilterItems(itemsSrc,gifPresent=True,metadataPresent=False,durationPos=False) #TODO TEST WITH STUB VID -> NO METADATA GENNABLE
    else:           items=FilterItems(itemsSrc,tumbNailPresent=True)

    assert len(items)>0,"FILTERED ALL ITEMS"
    if DEBUG:       print("items to draw:");printList(items)
    #items=[i for i in itemsSrc if i!=None and i.pathName!=None and i.imgPath!=None]
    try: vidItemsSorter(items,sort)        #sort with the target method
    except Exception as e: print("sorting items fail with: ",e)
    
    
    ##global flags for the user, used in _select, when an item is selected 
    PlayMode= tk.BooleanVar()
    RemoveModeEnable=tk.BooleanVar()
    DeleteGroupKeepOne=tk.BooleanVar()
    SegSelectionMode = tk.IntVar()
    buttonFrame = tk.Frame(root)
    buttonFrame.grid(row=0,column=0)
    nextPg = partial(_nextPage,items,drawGif,root)
    nextPage = tk.Button(buttonFrame, command=nextPg, text="nextPage", background="yellow")
    nextPage.grid(row=0, column=0)

    flushBtn = tk.Button(buttonFrame, command=_flushSelectedItems,\
        text="printSelected", background="green")
    flushBtn.grid(row=0, column=1)  #flush items selected (print + file write)

    segSelectionEnable = tk.Checkbutton(buttonFrame, text="segmentSelMode",\
        variable=SegSelectionMode) #TODO also flush->add: , command=_flushSelectedItems)
    segSelectionEnable.grid(row=1, column=0)

    SegSelectionTimes = tk.Entry(buttonFrame)
    SegSelectionTimes.insert(0, "10 30")
    SegSelectionTimes.grid(row=1, column=1)

    playModeEnable= tk.Checkbutton(buttonFrame, text="playMode",variable=PlayMode,\
        background="green")
    playModeEnable.grid(row=0, column=2)

    #remove items UI logic
    remMode= tk.Checkbutton(buttonFrame, text="removeMode",variable=RemoveModeEnable)
    remMode.grid(row=0,column=3)
    delGroup= tk.Checkbutton(buttonFrame, text="DelGroupKeepOne",variable=DeleteGroupKeepOne)
    delGroup.grid(row=0,column=4)
    remSel=partial(_removeSelected,SelectedList)
    delSelection=tk.Button(buttonFrame,command=remSel, text="DEL_SELECTED",background="red")
    delSelection.grid(row=0, column=5)


    #root.after_idle(_nextPage,items,drawGif,sFrame)
    nextPg()
    if not subWindow: root.mainloop()

    return SelectedList

def guiMinimalStartGroupsMode(groups,trgtAction=itemsGridViewStart,trgtActionExtraArgs=[],startSearch=".",sortOnGroupLen=True):
    """ @groups: dict of k-->itemsGroup to show on selection,
        @trgtAction: func to call on group select: items,[extraArgs] -> display
        @trgtActionExtraArgs: args to unpack & pass to @trgtAction after items

        When tkinter root closed, Returns SelectedList of items
    """
    global nextPage,SelectedList
    
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
    return SelectedList

if __name__ == "__main__": 

    startSearch="."
    if len(argv)>1 and argv[1]=="-h": print("usage: [start,selectionMode,useDumpItemsFilepath] ")
    if len(argv)>1: startSearch=argv[1]
    SEL_MODE="GROUPS"#"ITEMS"
    if len(argv)>2: SEL_MODE=argv[2]

    SELECTION_LOGFILE="/tmp/selection"
    grouppingFunc=ffmpegConcatDemuxerGroupping#ffmpegConcatFilterGroupping #

    #avoid fs scan -> reuse previous scanned items  in a tuple list json serialized file
    use_dump_items_founded=USE_DUMP_ITEMS_FOUNDED
    if len(argv)>3: use_dump_items_founded,ITEMS_LAST_FOUND,GROUPS_LAST_FOUND=True,argv[2],argv[2]

    start=perf_counter()

    try:        dumpFp = open(ITEMS_LAST_FOUND, "r")
    except:     use_dump_items_founded = False
    if use_dump_items_founded:        items = [VidTuple(*x) for x in load(dumpFp)]
    else:                             items = list(GetItems(startSearch, forceMetadataGen=False).values())
    endItemsGet = perf_counter()
    print("source items get in ", endItemsGet - start, "used previous dump ", use_dump_items_founded)
    items = FilterItems(items, metadataPresent=False, gifPresent=DRAW_GIF, tumbnailPresent=(not DRAW_GIF),durationPos=False)
    if not use_dump_items_founded: genMetadata(items)   #not possible gen missing metadata on named tuple
    if DUMP_ITEMS_FOUNDED and not use_dump_items_founded: dump([i.toTupleList() for i in items],open(ITEMS_LAST_FOUND, "w"))

    if SEL_MODE=="GROUPS":
        groups=GetGroups(items,grouppingRule=grouppingFunc,startSearch=startSearch,filterTumbnail=(not DRAW_GIF),filterGif=DRAW_GIF)
        endGroupGet=perf_counter()
        print("source group get in",endGroupGet-endItemsGet,"used previous dump ",use_dump_items_founded)
        groups=FilterGroups(groups,100,mode="dur") #filter small groups
        guiMinimalStartGroupsMode(groups,trgtActionExtraArgs=[True,True])
    else:       #ITEMS
        itemsGridViewStart(items,drawGif=DRAW_GIF)
