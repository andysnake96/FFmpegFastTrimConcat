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
import tkinter as tk
from tkinter import messagebox
from PIL import ImageTk, Image
from functools import partial
from MultimediaManagementSys import *
from os import environ as env
from copy import copy
from time import perf_counter
SelectedList = list()

BTN_SELECTED_THICKNESS=7
BTN_NN_SELECTED_THICKNESS=1
def _select(selected):
    """button pressed selecting selected item
    if in SegSelectionMode -> same items can be continuosly selected multiple times
    if normal mode re press on item cause de selection of last pressed
    will be append to  SelectedList ffmpeg cut string
    """
    global SelectedList
    global PlayMode, SegSelectionMode, SegSelectionTimes, RemoveModeEnable, DeleteGroupKeepOne
    global btns
    button=btns[selected.nameID]
    print("selected\t:",len(SelectedList))
    if RemoveModeEnable.get():
        target=[selected]
        if DeleteGroupKeepOne.get() and len(SelectedList)>0: 
            if target[0] not in SelectedList: SelectedList.append(target[0])
            target=SelectedList
            ## put the item leader of the selected at first position, selecting the one  with largerst size
            maxItemIdx,maxSize=0,target[0].sizeB
            for i in range(len(target)):
                if target[i].sizeB>maxSize: maxItemIdx,maxSize=i,target[i].sizeB
            target[0],target[maxItemIdx]=target[maxItemIdx],target[0]   
            groupLeader=target.pop(0)
        if messagebox.askyesno('REMOVE'+str(len(target)), 'Remove?',icon='warning'):
            for t in target:
                t.remove()
                button=btns[t.nameID]
                button.config(state="disabled")
                button.config(highlightbackground = "black", highlightcolor= "black",highlightthickness=BTN_NN_SELECTED_THICKNESS,borderwidth=BTN_NN_SELECTED_THICKNESS)
            btns[groupLeader.nameID].config(highlightbackground = "black", highlightcolor= "black",highlightthickness=BTN_NN_SELECTED_THICKNESS,borderwidth=BTN_NN_SELECTED_THICKNESS)
            del(selected,button)
        if DeleteGroupKeepOne.get(): SelectedList=list()    #empty the list in group delettion
        return
    if PlayMode.get(): return selected.play()
    button.config(highlightbackground = "red", highlightcolor= "red",highlightthickness=BTN_SELECTED_THICKNESS,borderwidth=BTN_SELECTED_THICKNESS)
    if SegSelectionMode.get() == 1:
        times = SegSelectionTimes.get().split(" ")
        #SelectedList.append("ffmpeg -ss " + times[0] + " -to " + times[-1] + " -i " + selected.pathName)
        selected.cutPoints.extend([times])
        print(selected.cutPoints)
    ## normal selection mode
    #if len(SelectedList) > 0 and SelectedList[-1] == selected:  # pop on re selection item
    if  selected in SelectedList:
        SelectedList.remove(selected)
        print("POPED: ", selected)
        button.flash()
        button.flash()
        button.config(highlightbackground = "black", highlightcolor= "black",highlightthickness=BTN_NN_SELECTED_THICKNESS,borderwidth=BTN_NN_SELECTED_THICKNESS)
    else:
        SelectedList.append(selected)


def buildFFmpegCuts(item):
    outStr=""
    for points in item.cutPoints:
        outStr+= "ffmpeg -i "+item.pathName+ "-ss "+str(points[0])+" -to"+str(points[1])+" out.mp4\n"
    return outStr
def _flushSelectedItems(selected=SelectedList):
    cumulativeSize = 0
    lines = list()
    for i in selected:
        #print(i.pathName, "\t\t ", int(i.sizeB) / 2 ** 20, " MB")
        if i.cutPoints!=[]: lines[-1]=buildFFmpegCuts(i) #ffmpeg cut standard
        else:               lines.append(i.pathName+"\n")
        cumulativeSize += int(i.sizeB)
    if SELECTION_LOGFILE != "":
        f = open(ctime().replace(" ", "_") + SELECTION_LOGFILE, "w")
        f.writelines(lines)
        f.close()
    SelectedList.clear()
    printList(lines)

class VerticalScrolledFrame(tk.Frame):
    """A pure Tkinter scrollable frame that actually works!
    * Use the 'interior' attribute to place widgets inside the scrollable frame
    * Construct and pack/place/grid normally
    * This frame only allows vertical scrolling
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


ITEMS_LIMIT = 256
pageN = -1
MainFrame = None


def _nextPage(root=None, nextItems=None):
    global pageN, items
    if nextItems == None: nextItems = items
    pageN += 1
    if pageN > len(items) / ITEMS_LIMIT: pageN = 0  # circular next page
    print("nextPage ", pageN, root)
    print(pageN)
    nextPage.configure(text="nextPage: ")
    drawItems(nextItems, ITEMS_LIMIT * pageN, ITEMS_LIMIT, True, root=root)

font = ("Arial", 15, "bold")
def _getImage(imgPath): 
    out=None
    if imgPath=="":     return out
    #try:                    out=ImageTk.PhotoImage(Image.open(imgPath))  
    try:                    out=Image.open(imgPath)
    except Exception as e:  print("invalid img at: ",imgPath,"\t\t",e)
    return out

def drawItems(items, itemsStart=0, itemsToDrawLimit=ITEMS_LIMIT, FILTER_PATH_NULL=False, filterSize=0, root=None):
    global MainFrame, RootTk
    global btns, imgs
    if MainFrame != None:                MainFrame.destroy()
    if root == None: root = RootTk
    MainFrame = VerticalScrolledFrame(root)
    MainFrame.grid()
    btns = dict()
    imgs = list()
    row, col, i = 5, 0, 0
    colSize = 5
    start=perf_counter()
    itemsTarget=items[itemsStart:itemsStart + itemsToDrawLimit]
    imgsArgs=[ i.imgPath for i in itemsTarget]  #imgs path 
    #get imgs from file paths if the ammount is above POOL threshold (avoid only overhead of pickle/deserialize/fork/pool)
    if len(imgsArgs)>POOL_TRESHOLD and False:       processed=list(concurrentPoolProcess(imgsArgs,_getImage,"badTumbNail",POOL_SIZE) )
    else:                                           processed=list(map(_getImage,imgsArgs))
    for  i in range(len(itemsTarget)):
        mitem=itemsTarget[i]
        funcTmp = partial(_select, mitem)
        try: tumbrl=ImageTk.PhotoImage(processed[i])
        except Exception as e: print(e);tumbrl=None
        if tumbrl!=None:
            txt = ""
            if mitem.duration != 0: txt += "len secs\t" + str(mitem.duration)
            if mitem.sizeB != 0:    txt += "\nsize bytes\t" + str(mitem.sizeB)
            btn = tk.Button(MainFrame.interior, image=tumbrl, text=txt, compound="center", command=funcTmp, font=font)
            #btns.append(btn)
            imgs.append(tumbrl)
        else:
            print("skipped item, tumbnail err",mitem.imgPath,mitem.pathName,mitem.nameID)
            continue

        btns[mitem.nameID]=btn
        print(mitem.nameID, mitem.imgPath, row, col, i)
        btn.grid(row=row, column=col)
        col += 1
        i += 1
        if col >= colSize:
            col = 0
            row += 1
    end=perf_counter()
    print("drawed: ",len(imgs),"in secs: ",end-start)
    # root.mainloop()


PlayMode=False


########      GUI CORE     ###############################
RootTk=None

def itemsGridViewStart(itemsSrc,sort="nameID"):
    """
    start a grid view of the given MultimediaObjects items in the global Rootk or into a newone if Null
    :param itemsSrc: items to show in the grid view
    :param sort:  how sort the items in the grid view, either duration,size,sizeName,shuffle,nameID
    """
    #sort either size,duration
    global nextPage, RootTk,items, RemoveModeEnable
    global PlayMode, SegSelectionMode, SegSelectionTimes, DeleteGroupKeepOne
    vidItemsSorter(itemsSrc,sort)        #sort with the target method
    # if tk root already defined -> create a new root for a new window
    if RootTk == None:
        root = RootTk = tk.Tk()
    else:
        root = tk.Toplevel(RootTk)  # shoud create a new window
    items=itemsSrc
    # root.resizable(True,True)
    np = partial(_nextPage, root)
    nextPage = tk.Button(root, command=np, text="nextPage", background="yellow")
    nextPage.grid(row=0, column=0)
    flushBtn = tk.Button(root, command=_flushSelectedItems, text="printSelectedMItems", background="green")
    flushBtn.grid(row=1, column=0)

    SegSelectionMode = tk.IntVar()
    segSelectionEnable = tk.Checkbutton(root, text="segSelectionEnable",variable=SegSelectionMode, command=_flushSelectedItems)
    segSelectionEnable.grid(row=2, column=0)
    SegSelectionTimes = tk.Entry(root)
    SegSelectionTimes.insert(0, "10 30")
    SegSelectionTimes.grid(row=2, column=1)

    PlayMode= tk.BooleanVar()
    playModeEnable= tk.Checkbutton(root, text="play",variable=PlayMode,width=10,heigh=4,background="green")
    playModeEnable.grid(row=3, column=0)
    RemoveModeEnable=tk.BooleanVar()
    remMode= tk.Checkbutton(root, text="remove",variable=RemoveModeEnable)
    remMode.grid(row=4,column=0)
    DeleteGroupKeepOne=tk.BooleanVar()
    delGroup= tk.Checkbutton(root, text="DeleteGroupKeepOne",variable=DeleteGroupKeepOne)
    delGroup.grid(row=4,column=1)

    _nextPage(root=root)
    RootTk.mainloop()

THRESHOLD_KEY_PRINT=133  #max chars to show in a button
def SelectWholeGroup(items,groupK):
    global SelectedList
    SelectedList=copy(items)
    print("selected group",groupK,"of :",SelectedList)

def guiMinimalStartGroupsMode(groupsStart=None, prefix=" ", sortOnGroupLen=True,trgtAction=itemsGridViewStart, grouppingRule=sizeBatching,startSearch="."):
    """ groupsStart: dict of k-->itemsGroup to show on selection
        trgtAction: function to call on group selection, with as arg the selected items,groupKey
    """
    global nextPage, groups, RootTk,SelectedList
    groups = groupsStart
    if groupsStart == "": groups = GetGroups(grouppingRule=grouppingRule,startSearch=startSearch)
    RootTk = tk.Tk()
    ScrolledFrameGroup = VerticalScrolledFrame(RootTk)
    ScrolledFrameGroup.grid()
    groupItems = list(groups.items())
    # sort items according to flag given
    if sortOnGroupLen:
        groupItems.sort(key=lambda i: len(i[1]), reverse=True)
    else:   #sort on groupKey
        groupItems.sort(key=lambda i: i[0], reverse=True)

    for k, items in groupItems:
        cumulativeSize, cumulativeDur = 0, 0
        for item in items:
            cumulativeDur += int(item.duration)
            cumulativeSize += int(item.sizeB)
        k=str(k)
        keyStr = k+ prefix
        if len(keyStr) > THRESHOLD_KEY_PRINT:
            keyStr = keyStr[:THRESHOLD_KEY_PRINT] + "... "
            widthIdx=k.lower().find("width")
            if widthIdx >= 0: keyStr=k[widthIdx:widthIdx+THRESHOLD_KEY_PRINT]+"... "
        groupBtnTxt = "groupK: " + keyStr + "\nnumElements: " + str(len(items)) + " totalSize: " + str(
            cumulativeSize / 2 ** 20) + "MB totalLenghtMins: " + str(cumulativeDur / 60)
        gotoGroup = partial(trgtAction, items, k)
        tk.Button(ScrolledFrameGroup, text=groupBtnTxt, command=gotoGroup).pack()
    RootTk.mainloop()
    return SelectedList
