#!/usr/bin/env python3
#Copyright Andrea Di Iorio
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

import tkinter as tk
from tkinter import messagebox
from PIL import ImageTk, Image
from functools import partial
from os import environ as env
from copy import copy
from time import perf_counter,ctime
from sys import stderr
from utils import printList
SelectedList = list()       #selection modified by GUI 
#helper to (de)highlight a button
btnSel=lambda btn: btn.config(highlightbackground="red",highlightcolor= "red",\
  highlightthickness=BTN_SELECTED_THICKNESS,borderwidth=BTN_SELECTED_THICKNESS)
btnOff=lambda btn: btn.config(highlightbackground="black",highlightcolor="black",\
  highlightthickness=BTN_NN_SELECTED_THICKNESS,borderwidth=BTN_NN_SELECTED_THICKNESS)
##global vars supporting this GUI
RootTk=None
#global flags touched by the user
#PlayMode= tk.BooleanVar()
#RemoveModeEnable=tk.BooleanVar()
#DeleteGroupKeepOne=tk.BooleanVar()
#SegSelectionMode = tk.IntVar()
#SegSelectionTimes = tk.Entry(root)

###button logics
def _removeSelected(remTarget=SelectedList):
    global SelectedList,btns
    if not messagebox.askyesno('REMOVE ALL '+str(len(remTarget)),'Del?',icon='warning'):
        return
    for i in remTarget:
        btn=btns[i.nameID]
        if not i.remove(): continue #not removed
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
                if not t.remove(): continue #not removed
                btnOff(button) #hide deletted item's btn
                button.config(state="disabled")
            del(button,btns[t.nameID],t)

        if DeleteGroupKeepOne.get(): SelectedList=list()
        return

    if SegSelectionMode.get() == 1:  #add cut points to the selected item
        times = [float(x) for x in SegSelectionTimes.get().strip().split(" ") ] #ITERATIVE_TRIM_SEL CALL LOGIC
        selected.cutPoints.extend([times])
        SelectedList.append(selected)
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
    for points in item.cutPoints:
        cutCmd= "ffmpeg "+" -ss "+str(points[0])+" -to "+str(points[1])+" -i "+item.pathName+" out.mp4\n"
        if seekOutputOpt:
            cutCmd= "ffmpeg -i "+item.pathName+ "-ss "+str(points[0])+" -to "+str(points[1])+" out.mp4\n"
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
        button=btns[i.nameID]
        btnOff(button) #hide deletted item's btn
    SelectedList.clear()

    print(selectionInfos)
    printList(lines)

class VerticalScrolledFrame(tk.Frame):
    """ Tkinter vertical scrollable frame 
        interior field to place widgets inside the scrollable frame
        Construct and pack/place/grid normally
    """

    def __init__(self, parent, *args, **kw):
        tk.Frame.__init__(self, parent, *args, **kw)

        # create a canvas object and a vertical scrollbar for scrolling it
        vscrollbar = tk.Scrollbar(self, orient=tk.VERTICAL,width=53,activebackground="green",bg="green")
        vscrollbar.pack(fill=tk.Y, side=tk.LEFT, expand=tk.FALSE)
        canvas = tk.Canvas(self, bd=0, highlightthickness=0, height=999, yscrollcommand=vscrollbar.set)
        # canvas.configure(scrollregion=canvas.bbox("all"))
        canvas.pack(side=tk.RIGHT, fill=tk.BOTH, expand=tk.TRUE)
        vscrollbar.config(command=canvas.yview)
        vscrollbar.bind("<MouseWheel>", canvas.yview)
        # reset the view
        canvas.xview_moveto(0)
        canvas.yview_moveto(0)

        canvas.bind("<MouseWheel>", canvas.yview)
        # create a frame inside the canvas which will be scrolled with it
        self.interior = interior = tk.Frame(canvas)
        interior_id = canvas.create_window(0, 0, window=interior, anchor=tk.NW)

        # track changes to the canvas and frame width and sync them,
        # also updating the scrollbar
        def _configure_interior(event):
            # update the scrollbars to match the size of the inner frame
            size = (interior.winfo_reqwidth(), interior.winfo_reqheight())
            canvas.config(scrollregion="0 0 %s %s" % size)
            if interior.winfo_reqwidth() != canvas.winfo_width():
                # update the canvas's width to fit the inner frame
                canvas.config(width=interior.winfo_reqwidth())

        interior.bind('<Configure>', _configure_interior)

        def _configure_canvas(event):
            if interior.winfo_reqwidth() != canvas.winfo_width():
                # update the inner frame's width to fill the canvas
                canvas.itemconfigure(interior_id, width=canvas.winfo_width())

        canvas.bind('<Configure>', _configure_canvas)


font = ("Arial", 15, "bold")
def _getImage(imgPath): 
    out=None
    if imgPath=="":     return out
    #try:                    out=ImageTk.PhotoImage(Image.open(imgPath))  
    try:                    out=Image.open(imgPath)
    except Exception as e:  print("invalid img at: ",imgPath,"\t\t",e)
    return out

pageN = -1
MainFrame = None

def _nextPage(root=None, nextItems=None):
    global pageN, items
    if nextItems == None: nextItems = items
    pageN += 1
    if pageN > len(items) / ITEMS_LIMIT: pageN = 0  # circular next page
    print("nextPage is:", pageN)
    nextPage.configure(text="nextPage: "+str(pageN))
    drawItems(nextItems, ITEMS_LIMIT * pageN, root=root)


def drawItems(items, itemsStart=0, itemsToDrawLimit=ITEMS_LIMIT, \
        FILTER_PATH_NULL=True, filterSize=0, root=None):
    """
        drap items's tumbnails images starting from index @itemsStart til
        @itemsToDrawLimit. also filtering of images to actually display possible
    """
    global MainFrame, RootTk
    global btns, imgs
    if MainFrame != None:                MainFrame.destroy()
    if root == None: root = RootTk
    MainFrame = VerticalScrolledFrame(root)
    MainFrame.grid()
    btns = dict()
    imgs = list()
    i,row, col,colSize= 0,6, 0,GUI_COLSIZE
    
    start=perf_counter()
    itemsTarget=items[itemsStart:itemsStart + itemsToDrawLimit]
    imgsArgs=[ i.imgPath for i in itemsTarget]  #imgs path 
    if len(imgsArgs)>POOL_TRESHOLD: #multi process image parsing
        print("worker pool concurrent image parsing")
        processed=list(concurrentPoolProcess(imgsArgs,_getImage,"badTumbNail",POOL_SIZE))
    else:   processed=list(map(_getImage,imgsArgs))  #serial

    for  i in range(len(itemsTarget)):
        mitem=itemsTarget[i]
        funcTmp = partial(_select, mitem)   #BIND FUNCTION FOR SELECTION
        try: tumbrl=ImageTk.PhotoImage(processed[i])
        except Exception as e: tumbrl=None;print("ImgParseErr:",e,file=stderr)
        
        if tumbrl!=None:
            txt = ""
            if mitem.duration != 0: txt += "len secs\t" + str(mitem.duration)
            if mitem.sizeB != 0:    txt += "\nsize bytes\t" + str(mitem.sizeB)
            btn = tk.Button(MainFrame.interior, image=tumbrl, text=txt, \
                compound="center",fg="white", command=funcTmp, font=font)
            imgs.append(tumbrl) #avoid garbage collector to free the parsed imgs
            btns[mitem.nameID]=btn
        else:
            print("skipped item",mitem.imgPath,mitem.pathName,mitem.nameID)
            continue

        if VERBOSE: print("Adding:",mitem.nameID, mitem.imgPath, row, col, i)
        btn.grid(row=row, column=col)
        col += 1;i += 1
        if col >= colSize:
            col = 0
            row += 1

    end=perf_counter()
    print("drawed: ",len(imgs),"in secs: ",end-start)
    # root.mainloop()



### GUI CORE
def itemsGridViewStart(itemsSrc,sort="size"):
    """
    start a grid view of the given items in the global tk root (new if None)
    @param itemsSrc: items to show in the grid view
    @param sort: items sorting, either: duration,size,sizeName,shuffle,nameID
    When tkinter root closed, Returns SelectedList of items
    """
    #sort either size,duration
    global nextPage, RootTk,items, RemoveModeEnable
    global PlayMode, SegSelectionMode, SegSelectionTimes, DeleteGroupKeepOne
    
    items=FilterItems(itemsSrc,tumbNailPresent=True)
    #items=[i for i in itemsSrc if i != None and i.pathName!=None and i.imgPath!=None]
    vidItemsSorter(items,sort)        #sort with the target method
    
    #TODO root tk
    # if tk root already defined -> create a new root for a new window
    if RootTk == None:  root = RootTk = tk.Tk()
    else:               root = tk.Toplevel(RootTk)  # shoud create a new window
    # root.resizable(True,True)
    
    ##global flags for the user 
    PlayMode= tk.BooleanVar()
    RemoveModeEnable=tk.BooleanVar()
    DeleteGroupKeepOne=tk.BooleanVar()
    SegSelectionMode = tk.IntVar()
    SegSelectionTimes = tk.Entry(root)



    np = partial(_nextPage, root) #TODO partial(_nextPage, root,itemsSrc) 
    nextPage = tk.Button(root, command=np, text="nextPage", background="yellow")
    nextPage.grid(row=0, column=0)
    flushBtn = tk.Button(root, command=_flushSelectedItems,\
        text="printSelectedMItems", background="green")
    flushBtn.grid(row=1, column=0)

    segSelectionEnable = tk.Checkbutton(root, text="segSelectionEnable",\
        variable=SegSelectionMode) #TODO also flush->add: , command=_flushSelectedItems)
    segSelectionEnable.grid(row=2, column=0)
    SegSelectionTimes.insert(0, "10 30")
    SegSelectionTimes.grid(row=2, column=1)
    playModeEnable= tk.Checkbutton(root, text="play",variable=PlayMode,\
        width=10,heigh=4,background="green")
    playModeEnable.grid(row=3, column=0)
    #remove UI logic
    remMode= tk.Checkbutton(root, text="remove mode",variable=RemoveModeEnable)
    remMode.grid(row=4,column=0)
    delGroup= tk.Checkbutton(root, text="DelGroupKeepOne",variable=DeleteGroupKeepOne)
    delGroup.grid(row=4,column=1)
    remSel=partial(_removeSelected,SelectedList)
    delSelection=tk.Button(root,command=remSel, text="DEL-SELECTION",background="red")
    delSelection.grid(row=5, column=0)

    _nextPage(root=root)
    root.mainloop()
    return SelectedList

def guiMinimalStartGroupsMode(groupsStart=None,prefix=" ",sortOnGroupLen=True,\
        trgtAction=itemsGridViewStart, grouppingRule=sizeBatching,startSearch="."):
    """ @param groupsStart: dict of k-->itemsGroup to show on selection,
            if None, group items founded from @startSearch with @grouppingRule
        @param trgtAction: function to call on group selection: items -> display
        @param grouppingRule: if required, how to group items founded 
            from @startSearch

        When tkinter root closed, Returns SelectedList of items
    """
    global nextPage, RootTk,SelectedList


    if groupsStart == None: 
        groupsStart=GetGroups(grouppingRule=grouppingRule,startSearch=startSearch\
            ,filterTumbNailPresent=True)
        groupsStart=FilterGroups(groupsStart,5,mode="len")  #filter away little groups
    RootTk = tk.Tk()
    ScrolledFrameGroup = VerticalScrolledFrame(RootTk)
    ScrolledFrameGroup.grid()

    groupItems = list(groupsStart.items())
    if sortOnGroupLen:
        groupItems.sort(key=lambda i: len(i[1]), reverse=True)
    else:               #sort on groupKey
        groupItems.sort(key=lambda i: i[0], reverse=True)

    for k, items in groupItems:
        cumulativeSize, cumulativeDur = 0, 0
        for item in items:
            cumulativeDur += int(item.duration)
            cumulativeSize += int(item.sizeB)
        #for each group key, display the core part
        k=str(k)
        keyStr = k+ prefix
        if len(keyStr) > THRESHOLD_KEY_PRINT:
            keyStr = keyStr[:THRESHOLD_KEY_PRINT] + "... "
            widthIdx=k.lower().find("width") #if found show from resolution width
            if widthIdx >= 0: keyStr=k[widthIdx:widthIdx+THRESHOLD_KEY_PRINT]+"... "

        groupBtnTxt = "groupK: " + keyStr + "\nnumElements: " + str(len(items))\
         + " size: "+str(cumulativeSize/2**20)+"MB dur: "+str(cumulativeDur/60)
        gotoGroup = partial(trgtAction, items)
        tk.Button(ScrolledFrameGroup, text=groupBtnTxt,command=gotoGroup).pack()#TODO GRID?

    RootTk.mainloop()
    return SelectedList

if __name__ == "__main__": 

    SELECTION_LOGFILE="/tmp/selection"
    grouppingFunc=ffmpegConcatFilterGroupping #ffmpegConcatDemuxerGroupping
    #guiMinimalStartGroupsMode(grouppingRule=grouppingFunc)
    itemsGridViewStart(list(GetItems(".").values()))
