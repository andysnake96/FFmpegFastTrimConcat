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
"""
Flexible concatenation of videos by script generation for ffmpeg
to support re encodingless video concat videos are groupped by common metadata with FlexibleGroupByFields function
groupped video items can be segmentated with GenVideoCutSegmentsRnd, that from a video metadata will be output segments [[start,end]...] points 
    segments gen is per video, with flexible configuration (e.g. random seg, full possible seg, skip start portion end portion, ...)
    cutting video in segment is configured by a field setting on a copy of SegGenOptionsDflt
    seg generation can be graphically visualized with _debug_graph_turtle_segments function
    possible non default rnd seg generation based on the seg len proportional to src vid len with MODE_DURATION  option in SegGenOptionsDflt derivated dict
generated segments will refer to a script (dflt named genSegs.sh) that will cut videos by ffmpeg -ss -to (see lambdas for alternative cutting methods )
segments can be merged together with either ffmpeg concat filter or concat demuxer ( the former require re encoding, and with large num of segments is aggressive on mem usage )
respectivelly can be generated concatFilter.sh concat.list (latter to use with ffmpeg concat demuxer.. see ffmpegConcatDemuxVideos.sh )
- from ffmpeg doc, concat demuxer work at stream level with videos  with same codec,time base,... --> good try can be groupping by all fields excluding ["duration","bit_rate","nb_frames","tags","disposition","avg_frame_rate","color"] -
see argParseMinimal or -h for optional parameters
dependency to my MultimediaManagementSys for few functions and MultimediaItem class(rappresenting videos and metadatas)
_________________________________________________________________

ENV OVERRIDE OPTION
ENCODE: str for encode out video (dflt Nvidia h264 in FFmpegNvidiaAwareEncode)
DECODE: str for decode in video (dflt Nvidia h264 in FFmpegNvidiaAwareDecode)
FFMPEG: target ffmpeg build to use (dflt Nvidia builded one )

"""

from json import loads,dumps
from copy import deepcopy
from os import environ as env   #EXPORT DIFFERENT START REC SEARCH WITH START_SEARCH
import argparse
from sys import argv
############# 
###
env["REAL_PATH"]="True" #will export print mode correctly
PATH_SEP=":"
FFmpegNvidiaAwareDecode=" -vsync 0 -hwaccel cuvid -c:v h264_cuvid "
FFmpegNvidiaAwareEncode=" -c:v h264_nvenc "
FFmpegNvidiaAwareEncode+=" -preset fast -coder vlc "
FFmpegDbg=" -hide_banner -y -loglevel 'verbose' "
FFmpegNvidiaAwareBuildPath="/home/andysnake/ffmpeg/bin/nv/ffmpeg_g "+FFmpegDbg
FFmpegBasePath="~/ffmpeg/bin/ffmpeg "
FFMPEG=FFmpegNvidiaAwareBuildPath
## copy->nvenc  -c:v h264_nvenc -preset fast -coder vlc 
# ovveride (d)encoding
Encode=FFmpegNvidiaAwareEncode
Decode=FFmpegNvidiaAwareDecode
if env.get("ENCODE")!=None: Encode=env("ENCODE")
if env.get("DECODE")!=None: Decode=env("DECODE")
if env.get("FFMPEG")!=None: FFMPEG=env("FFMPEG")
#ffprobe -v quiet -print_format json -show_format -show_streams $1 > $1.json
from GUI import *
from MultimediaManagementSys import *
from random import random,randint

_getVideoStreamDictFromPath=lambda fpath: load(open(fpath))["streams"][0]
def FlexibleGroupByFields(multimediaItems,groupKeysList,EXCLUDE_ON_KEYLIST=False,EXCLUDE_WILDCARD=True):
    """
    group multimedia metadata in on the base of their value on a given list of common fileds expressed in groupKeysList
    if EXCLUDE_ON_KEYLIST is true the groupping will be based on values of all fields not in groupKeysList 
        so groupKeysList  will act as a black list actually
    returned dict of [grouppingKeys]-->[videoInGroup0MultimediaItem,video1MultimediaItem,....]
    """
    groupsDict=dict()   #dict (valueOfK_0,...,valueOfK_N) -> LIST Files with this metadata values groupped
    groupKeysList.sort()
    for item in multimediaItems:
        fMetadata=item.metadata[0]  #get video stream of multimedia obj.metadata
        fMetadataValues=list()  #list of values associated to groupKeysList for the target groupping of files
        fKeysAll=list(fMetadata.keys())
        fKeysAll.sort()
        for k in fKeysAll:
            if EXCLUDE_ON_KEYLIST:  #the given groupKeysList is a black list
                if EXCLUDE_WILDCARD:    #blackList will be used has a pattern to exclude actual f metadata keys
                    kInExcludeList=False
                    for kEx in groupKeysList:
                        if kEx in k:
                            kInExcludeList=True
                            break
                    if kInExcludeList==False:fMetadataValues.append((k,fMetadata[k]))
                else:
                    if k not in groupKeysList: fMetadataValues.append((k,fMetadata[k]))
            else:
                if k in groupKeysList: fMetadataValues.append((k,fMetadata[k]))
        groupK=tuple(fMetadataValues)
        try:    #avoid unhashable contained types??
            if groupsDict.get(groupK)==None: groupsDict[groupK]=list()  #create a new list for target values of groupKeysList
        except: continue
        #finally append to target group list the processed file
        groupsDict[groupK].append(item)
    return groupsDict
#rand segment cutting from item
#cutting constr specification
MODE_DURATION="MODE_DURATION" #time identified as floating point in (0,1) as a proportion of the full time of the mItem
MODE_ABSTIME="MODE_ABSTIME"   #time points specified as num of second
################## dflt concat configuration
CONCAT_FILELIST_FNAME,BASH_BATCH_SEGS_GEN,CONCAT_FILTER_FILE="concat.list","genSegs.sh","CONCAT_FILTER_FILE"
SegGenOptionsDflt={"segsLenSecMin":None,"segsLenSecMax":None,"maxSegN":1,"minStartConstr":0,"maxEndConstr":None,"mode":MODE_ABSTIME }
def GenVideoCutSegmentsRnd(mItem,segGenConfig=SegGenOptionsDflt,MORE_SEGN_THREASHOLD_DUR_SEC=596,SEG_END_OUT_EXPLICIT=True,ROUND_INT=True):
    """
    generate random segment identified by start/end point in abs time in seconds returned as [(s1Start,s1End),(s2Start,s2End),...]
    minStartConstr maxEndConstr identify respectivelly constraint in start/end for the segments
    maxEndConstr may be specified as an absolute end time (as a positive num) or as a negative time, the abs will be subtracted to target duration of mItem
    if minSegLen/maxSegLen is None -> it will be set to max allowable duration [costrained by maxEndConstr ]
    mode specify how this costraint and min/maxSegLen has to be interpreted (see above constants documentation=
    multiple segment will be allocated in different portions, not overlapped if parameter expressed correctly
    enable more likelly max SEG N alloc on long item if duration is above MORE_SEGN_THREASHOLD_DUR_SEC
    if MORE_SEGN_THREASHOLD_DUR_SEC is 0 the segN will be selected random uniformly
    SEG_END_OUT_EXPLICIT True => output seg end as abs time, otherwise out as duration
    """

    #### get seg gen option in vars
    maxEndConstr=segGenConfig["maxEndConstr"]
    minStartConstr=segGenConfig["minStartConstr"]
    mode=segGenConfig["mode"]
    maxSegN=segGenConfig["maxSegN"]
    minSegLen=segGenConfig["segsLenSecMin"]
    maxSegLen=segGenConfig["segsLenSecMax"]
    duration=mItem.duration

    ## time constraint in segment in cut
    duration-=minStartConstr    #resize duration if given start constr (not allocable seg insideit) ... dflt constr is 0
    if maxEndConstr!=None:  #duration override for costum maxEndConstr constraint  
        if maxEndConstr>0 and maxEndConstr < duration: duration=maxEndConstr-minStartConstr
        elif maxEndConstr<0: duration+=maxEndConstr #subtrack maxEndConstr from duration
    #if max/min seg len is None => get the full possible duration [ pre costrained ]
    if maxSegLen==None: maxSegLen=duration
    if minSegLen==None: minSegLen=duration

    nSeg=randint(1,maxSegN)         #basic rand seg N decision else
    if MORE_SEGN_THREASHOLD_DUR_SEC>0 and duration>=MORE_SEGN_THREASHOLD_DUR_SEC:
        nSeg=max(nSeg,maxSegN-nSeg)
    ########## gen random segs inside solts of totDur/nSeg
    outSegs=list()  #list of [(startSegSec,endSegSec),...]
    segmentSlotLen=float(duration)/nSeg 
    segmentSlotLenTotProportion=segmentSlotLen/duration
    start=max(0,minStartConstr) #base time for start slot time generation; changed to slot start at each iteration of seg gen
    for x in range(nSeg): #segment times genration in different slots NB minMax SegLen has to be setted correctly
        ## MODE_ABSTIME
        segLen=(random()*(maxSegLen-minSegLen))+minSegLen
        #assure seg alloc inside slot
        segStart=start+random()*(segmentSlotLen-segLen) #actual start for segment random placed in the whole avaible space inside the curr slot
        ## MODE_DURATION
        if mode==MODE_DURATION:
            start-=x*segmentSlotLen #revert MODE_ABSTIME mod on seg base start
            start+=x*segmentSlotLenTotProportion
            segStart=duration*(start+random()*(segmentSlotLenTotProportion-segLen))
            segLen*=duration
        ###alloc generated segment
        if ROUND_INT:
            segStart=int(segStart)
            segLen=int(segLen)
        segEndOut=segStart+segLen
        if not SEG_END_OUT_EXPLICIT: segEndOut=segLen   #output for ffmpeg -ss -t; otherise -ss -to
        outSegs.append((segStart,segEndOut))
        start=x*segmentSlotLen          #start for the next iteration
    return outSegs

def _debug_graph_turtle_segments(itemSegmentList,SCREEN_W=700,EXTRA_WIDTH_STRINGS=500,SEGS_FNAME="segments.eps"):
    """
    draw a new line on canvas with in black item duration in green segment allocated
    each new line will be drawn down of 2 unit
    the size of each line will be proportional to corresponding element normalized to the longest item
    """
    import turtle

    sc=turtle.Screen()
    turtle.tracer(0, 0)
    LINE_WIDTH=15
    SCREEN_H=len(itemSegmentList*LINE_WIDTH)+22
    FONT=("Arial",6,"normal")
    sc.setup(SCREEN_W,len(itemSegmentList)*LINE_WIDTH)
    sc.setworldcoordinates(0,0,SCREEN_W+EXTRA_WIDTH_STRINGS,SCREEN_H)
    END_X=SCREEN_W+EXTRA_WIDTH_STRINGS
    turtle.setpos(0,SCREEN_H-10)
    turtle.speed(0)
    durs=list()
    for i,s in itemSegmentList:
        durs.append(i.duration)
    maxDur=max(durs)
    turtle.up()
    for item,segs in itemSegmentList:
        turtle.down()
        pos=turtle.pos()
        turtle.color("black")
        turtle.width(1)
        turtle.forward((item.duration/maxDur)*SCREEN_W) #duration
        turtle.setpos(pos)
        turtle.color("green")
        turtle.width(3)
        for s in segs:
            turtle.up()
            turtle.setpos(pos)
            turtle.forward((((s[0])/maxDur)*SCREEN_W))         #seek to segment start
            turtle.down()
            turtle.forward(((s[1]-s[0])/maxDur)*SCREEN_W)    #draw segment
        #move down for next line
        turtle.up()
        if EXTRA_WIDTH_STRINGS>0:
            turtle.setpos(pos)
            turtle.forward((item.duration/maxDur)*SCREEN_W+20) #duration
            #draw a dotted line until END
            turtle.color("black")
            DOT_STEP=50
            turtle.width(1)
            while turtle.pos()[0]<END_X:
                turtle.forward(DOT_STEP)
                turtle.dot(1)
            turtle.setx(END_X)
            turtle.write(str(item.duration)+" - "+str(segs),False,"right",FONT)
        turtle.setpos(pos)
        turtle.sety(pos[1]-LINE_WIDTH)
    #save rappresentation of  segments generated and freeze image
    turtle.getscreen().getcanvas().postscript(file=SEGS_FNAME)
    turtle.done()
    turtle.update()
    input()
def _cleanPathname(name,disableExtensionForce=False,extensionTarget=".mp4"):
    #clean pathName assuring it will be like 'XXXXX.extensionTarget'
    if len(name)<3: return
    if name[0]!="'": name="'"+name
    if name[-1]!="'": name=name+"'"
    if not disableExtensionForce and extensionTarget not in name:
        name=name[:-1]+extensionTarget+"'"
    return name

## SEG CUT CMD GEN
#RE-ENCODINGLESS
## cut a selected segment of video with seek options as input or output(more accurate ??)
buildFFMPEG_segExtractNoReencode=lambda pathName,segStart,segTo,destPath:FFMPEG+" -ss "+str(segStart)+" -to "+str(int(segTo))+" -i '"+pathName+"' -c copy -avoid_negative_ts 1 "+_cleanPathname(destPath)
buildFFMPEG_segExtractPreciseNoReencode=lambda pathName,segStart,segTo,destPath:FFMPEG+Decode+" -i "+pathName+" -ss "+str(segStart)+" -to "+str(int(segTo))+" -c copy '"+destPath+"'"
#RE-ENCODING
buildFFMPEG_segTrimPreSeek=lambda pathName,segStart,segTo,destPath:FFMPEG+" -ss "+str(segStart)+" -i "+pathName+" -vf trim="+str(segStart)+":"+str(segTo)+Encode+"'"+destPath+"'" #trim filter
buildFFMPEG_segTrim=lambda pathName,segStart,segTo,destPath:FFMPEG+Decode+" -ss "+str(segStart)+" -i "+pathName+" -vf trim="+str(segStart)+":"+str(segTo)+Encode+"'"+destPath+"'" #trim filter
buildFFMPEG_segExtract_reencode=lambda pathName,segStart,segTo,destPath: FFMPEG+Decode+" -ss "+str(segStart)+" -to "+str(segTo)+" -i '"+pathName+"'"+Encode+"'"+destPath+"'"    #seek and re encode
##

BASH_NEWLINE_CONTINUE="\\\n"
MULTILINE_OUT=True
def concatFilterCmd(items,outFname="/tmp/out.mp4",ONTHEFLY_PIPE=True,PIPE_FORMAT="matroska",HwDecoding=False):
    """
    generate ffmpeg concat filter cmd string, to concat items specified segments
    items: list of vids path to concat 
    optional output to a pipe to ffplay ( ffmpeg ... - | ffplay -) can be selected with ONTHEFLY_PIPE and PIPE_FORMAT
    HwDecoding: flag to enable hw decoding on each vid
    """
    outStrCmd=FFMPEG
    inputsFiles=list()  # list of input lines
    numInputs=len(items)
    for itemPath in items:
        itemLine=" -i '"+itemPath+"'\t"
        inputsFiles.append(itemLine)
    shuffle(inputsFiles)            #shuf segment list as input operand
    prfx=BASH_NEWLINE_CONTINUE
    if HwDecoding: prfx+=Decode     #HW decoding for each input vid
    inputBlock=prfx+ prfx.join(inputsFiles) #join in segment shuffled with as prefix \+\n and eventual Decode option
    outStrCmd+=inputBlock+BASH_NEWLINE_CONTINUE
    # gen concat filter streams string [1][2]..
    concatFilterInStreamsString=""
    for x in range(numInputs): concatFilterInStreamsString+="["+str(x)+"]"
    outStrCmd+=' -filter_complex "'+concatFilterInStreamsString+"concat=n="+str(numInputs)+':v=1:a=1"'
    outStrCmd+=" -vsync 2"      
    targetOutput=" "+outFname
    outStrCmd+=Encode
    if ONTHEFLY_PIPE: targetOutput=" -f "+PIPE_FORMAT+" - | ffplay - " #on the fly generate and play with ffplay
    outStrCmd+=targetOutput
    return outStrCmd
def FFmpegConcatFilter(itemsList,outScriptFname,onTheFlayFFPlay=False):
    """
    concat itemsList of MultimediaItems with ffmpeg concat filter
    """
    itemsPaths=[i.pathName for i in itemsList]
    print(itemsList,itemsPaths)
    outFp=open(outScriptFname,"w")
    ffmpegConcatFilterCmd=concatFilterCmd(itemsPaths,ONTHEFLY_PIPE=onTheFlayFFPlay)
    outFp.write(ffmpegConcatFilterCmd)
    outFp.close()


def FFmpegTrimConcatFlexible(itemsList, SEG_BUILD_METHOD=buildFFMPEG_segExtractNoReencode,segGenConfig=None,**opts):
    """
        support cutting segments from videos in itemsList and later merging back by generation of ffmpeg bash scripts
        SEG_BUILD_METHOD is the function used to gen the video segment in the BASH_BATCH_SEGS_GEN script
            basically the script will write generated segments in tmpCut/SRC_VIDEO_NAME_K/i.mp4  where i is in 0...n, n is num of generated segs from the vid
            [usefull commented line in the script will mount tmpCut generated root dir for segs as tmpfs -> segmentation will be fast executed in ram]
        segGenConfig is an override on the default segment gen rule applied to each video in itemsList
        if item has already inside defined a list of cutPoints as [[start,end]..], that times will be used to cut the item
            if start,end has been specified to None -> will be setted to the min/max allowable
        itemsList has to have both the main fields pathName, metadata otherwise is ignored
        opts: BASH_BATCH_SEGS_GEN, CONCAT_FILELIST_FNAME, CONCAT_FILTER_FILE -> respectivelly for cut script gen, concat demuxer list file, concatFilter script gen
        possible embed in itemsList element as [elem,[startTime,endTime]] that will override min/maxEndConstr field of seg generation for that video only
                                            empty val for this config is -1
    """
    global CONCURRENCY_LEVEL_FFMPEG_BUILD_SEGS
    itemSegmentsList,trgtSegsList,trgtDirsList,ffmpegSegBuildCmds=list(),list(),list(),list()
    TRAIL_CMD_SUFFIX="\n"
    if CONCURRENCY_LEVEL_FFMPEG_BUILD_SEGS>0: TRAIL_CMD_SUFFIX=" & \n"
    j=0
    #parse given opts
    #destination path override
    if opts.get("BASH_BATCH_SEGS_GEN")!=None: bash_batch_segs_gen=opts["BASH_BATCH_SEGS_GEN"]
    if opts.get("CONCAT_FILELIST_FNAME")!=None: concat_file_list=opts["CONCAT_FILELIST_FNAME"]
    storeSegmentationChoiced=False
    if opts.get("STORE_SEGMENTATION_INFO")!=None: storeSegmentationChoiced=opts["STORE_SEGMENTATION_INFO"]
    if segGenConfig==None: segGenConfig=deepcopy(SegGenOptionsDflt)
    for item in itemsList:
        if item.pathName=="" or item.sizeB==0: continue     #skip malformed itmes... redundant

        #############   SEGs GENERATION     #############################################

        segs=item.cutPoints #segmentation point may be already defined for current item (e.g. MANUAL SELECTION BY SelectItemPlay
        if segs==list():    segs=GenVideoCutSegmentsRnd(item,segGenConfig)
        if storeSegmentationChoiced:    item.cutPoints=segs #store segmentation choiced for current item
        ##########################################
        itemSegmentsList.append((item,segs))        #TODO DEBUG SEG GENERATION ONLY
        print(segs,item.duration)
        trgtDir="tmpCut/"+item.nameID
        trgtDirsList.append("mkdir '"+trgtDir+"'\n")
        #get allowable min start-end max  time points for current items from the given configuration
        startMinAllowable,endMaxAllowable=0,item.duration
        if segGenConfig["minStartConstr"]!=None:startMinAllowable=segGenConfig["minStartConstr"]
        if segGenConfig["maxEndConstr"]!=None:endMaxAllowable=segGenConfig["maxEndConstr"]
        for s in range(len(segs)):
            trgtSegDestPathName=trgtDir+"/"+str(s)+"."+item.extension
            #trgtSegsList.append("file\t"+trgtSegDestPathName+"\n")
            trgtSegsList.append(trgtSegDestPathName)
            #segment start-to may be setted to NULL in manual selection mode --> set to min/max allowable from config
            start,to=segs[s][0],segs[s][1]
            if start==None: start=startMinAllowable
            if to==None: to=endMaxAllowable
            if to<0: to=item.duration+to
            ffmpegSegBuildCmds.append(SEG_BUILD_METHOD(item.pathName,start,to,trgtSegDestPathName)+TRAIL_CMD_SUFFIX)
            #interleave build cmd with wait to concurrency build fixed num of vids
            if CONCURRENCY_LEVEL_FFMPEG_BUILD_SEGS>0 and j%CONCURRENCY_LEVEL_FFMPEG_BUILD_SEGS==0:  ffmpegSegBuildCmds.append("wait\n")    
            j+=1
            #print(ffmpegSegBuildCmds[-1])

        #write bash ffmpeg build segs
    bashBatchSegGen=open(bash_batch_segs_gen,"w")
    bashBatchSegGen.write("mkdir tmpCut\n#sudo mount -t tmpfs none tmpCut\n")
    bashBatchSegGen.write("#rm -r tmpCut/*\n")
    bashBatchSegGen.writelines(trgtDirsList)        #write dirs to make
    bashBatchSegGen.writelines(ffmpegSegBuildCmds)  #write ffmpeg cmds
    bashBatchSegGen.write("\nwait\necho DONE")                 #wait concurrent ffmpeg seg builds
    #write output segment file list
    shuffle(trgtSegsList)
    file=open(concat_file_list,"w")
    file.writelines("file\t"+"\nfile\t".join(trgtSegsList))
    file.close()
    if "CONCAT_FILTER_FILE" in opts:
        concatFilterFile=opts["CONCAT_FILTER_FILE"]
        concatStr=concatFilterCmd(trgtSegsList,ONTHEFLY_PIPE=False)
        concatBashSegs=open(concatFilterFile,"w")
        concatBashSegs.write(concatStr)
        concatBashSegs.close()

    #_debug_graph_turtle_segments(itemSegmentsList)

#TARGETS SELECTION OPTIONS
TAKE_ALL_MOST_POPOLOUS="TAKE_ALL_MOST_POPOLOUS"
GUI_TUMBNAIL_GROUPS_SELECT="GUI_TUMBNAIL_GROUPS_SELECT"
GUI_GROUPS_SELECT="GUI_GROUPS_SELECT"
ITERATIVE_PLAY_CONFIRM="ITERATIVE_PLAY_CONFIRM"
def _select_items_group(items,keyGroup):
    global SelectedGroupK
    SelectedGroupK=keyGroup

#GROUP KEYS--------------------------
GroupKeys=["width","height","sample_aspect_ratio"]
#groupKeys=["duration"]
#ECLUDE KEYS-------------------------
#excludeGroupKeys=["bit_rate","nb_frames","tags","disposition","avg_frame_rate","color","index"]
#ExcludeGroupKeys=["duration","bit_rate","nb_frames","tags","disposition","has_b_frame","avg_frame_rate","color"]
ExcludeGroupKeys=["bit_rate","nb_frames","tags","disposition","has_b_frame","avg_frame_rate","color"]
#excludeGroupKeys=["rate","tags","disposition","color","index","refs"]

def argParseMinimal(args):
    #minimal arg parse use to parse optional args
    parser=argparse.ArgumentParser(description='group Video for concat flexible\n concat generated segments from groupped videos')
    parser.add_argument("pathStart",type=str,default=".",help="path to start recursive search of vids")
    parser.add_argument("--maxEndConstr",type=float,default=None,help="costum max end allowable for segments")
    parser.add_argument("--minStartConstr",type=float,default=None,help="costum min start allowable for segments")
    parser.add_argument("--segsLenSecMax",type=int,default=None,help="")
    parser.add_argument("--segsLenSecMin",type=int,default=None,help="")
    parser.add_argument("--maxSegN",type=int,default=None,help="")
    parser.add_argument("--groupSelectionMode",type=str,choices=["GUI_TUMBNAIL_GROUPS_SELECT","ITERATIVE_PLAY_CONFIRM","TAKE_ALL_MOST_POPOLOUS","GUI_GROUPS_SELECT"],default="GUI_TUMBNAIL_GROUPS_SELECT",help="mode of selecting groups to concat")
    #parser.add_argument("--grouppingRule",type=str,default=ffmpegConcatDemuxerGroupping.__name__,choices=list(GrouppingFunctions.keys()),help="groupping mode of items")
    parser.add_argument("--concurrencyLev",type=int,default=2,help="concurrency in cutting operation (override env CONCURRENCY_LEVEL_FFMPEG_BUILD_SEGS)")
    parser.add_argument("--parseSelectionFile",type=str,default=None,help="set serialized file  videos metadata and eventual cutPoint times to group and merge with the standard  scan")
    parser.add_argument("--groupDirect",type=bool,default=False,help="group metadata founded by direct groupping keys embedded in code")
    parser.add_argument("--justFFmpegConcatFilter",type=bool,default=False,help="concat selected items with ffmpeg's concat filter")
    parser.add_argument("--justMetadata",type=bool,default=False,help="pathname is not mandatory to be founded during item scan")
    parser.add_argument("--genGroupFilenames",type=int,choices=[0,1,2],default=0,help="gen newline separated list of file paths for each founded group: 0=OFF,1=ON,2=JUST GEN groupFnames, no segmentation, cumulative time is logged before each file path with a line starting with #")
    parser.add_argument("--genGroupFilenameShuffle",type=bool,default=True,help="shuffle order of item to write in genGroupFilenames")
    parser.add_argument("--genGroupFilenamesPrefix",type=str,default="file ",help="prefix to append at each line of the generated file with genGroupFilenames")
    return parser.parse_args(args)

if __name__=="__main__":
    #export NameIdFirstDot=False && python3 groupVideoConcat.py  /home/andysnake/WIN/Users/andysnake/Downloads/pluperpassLinks   --parseSelectionFile selectionlist.json --minStartConstr 8 --maxEndConstr -5.5 --maxSegN 1 --groupSelectionMode ITERATIVE_PLAY_CONFIRM

    #/home/andysnake/DATA2/all/all:/home/andysnake/Video/Nj    --minStartConstr 11 --maxEndConstr -12.5 --maxSegN 3 --segsLenSecMax 10 --segsLenSecMin 4 --groupSelectionMode GUI_TUMBNAIL_GROUPS_SELECT
    #populate segment generator with ovverrided deflt configuration by optional args parsed with argparse
    nsArgParsed=argParseMinimal(argv[1:])
    print(__doc__)
    segGenConfig=deepcopy(SegGenOptionsDflt)
    for k in SegGenOptionsDflt.keys():
        if k not in nsArgParsed: continue
        opt=nsArgParsed.__dict__[k]
        if opt!=None: segGenConfig[k]=opt
    #env override
    selectTargetItems=TAKE_ALL_MOST_POPOLOUS
    startPath=nsArgParsed.pathStart
    Take=nsArgParsed.groupSelectionMode
    GUI_SELECT_GROUP_ITEMS=True             #if ITERATIVE_PLAY_CONFIRM: select group on gui
    global CONCURRENCY_LEVEL_FFMPEG_BUILD_SEGS
    CONCURRENCY_LEVEL_FFMPEG_BUILD_SEGS=nsArgParsed.concurrencyLev
    print("Config with:\t",startPath,Take,CONCURRENCY_LEVEL_FFMPEG_BUILD_SEGS)
    ### getting items
    startPath=[startPath]
    if PATH_SEP in nsArgParsed.pathStart: startPath=nsArgParsed.pathStart.split(PATH_SEP)
    mItemsDict,grouppingsOld=dict(),dict()
    for path in startPath:
        mItemsDict=GetItems(path,mItemsDict,True)
            
    #filter away videos mis formed
    itemsToGroup=list()    
    for v in mItemsDict.values():
        if v.metadata!="" and ( nsArgParsed.justMetadata or v.pathName!=""):    itemsToGroup.append(v)
    if len(itemsToGroup)==0: raise Exception("NOT FOUNDED COMPATIBLE VIDEOS AT "+str(startPath))
    ####### GROUP VIDEOS BY COMMON PARAMS IN METADATA
    # either group by common defined fields (GroupKeys) or by all field but few defined (ExcludeGroupKeys)
    
    ############### ACTUAL GROUPPING    #############################

    ##TOGLE NEXT 2 PAIR OF  LINES FOR GROUPPING BY FEW FIELDS (concatFilter) or almost all fields (concatDemuxer)
    # excludeOnKeyList,excludeWildcard=False,True
    # groupByFields=groupKeys
    excludeOnKeyList,excludeWildcard=True,True
    groupByFields=ExcludeGroupKeys
    if nsArgParsed.groupDirect: #overwrite dflt on arg -> group by groupKeys without excludsion
        excludeOnKeyList,excludeWildcard=False,False
        groupByFields=GroupKeys
    grouppings=FlexibleGroupByFields(itemsToGroup, groupByFields, EXCLUDE_ON_KEYLIST=excludeOnKeyList, EXCLUDE_WILDCARD=excludeWildcard)
    # group eventual serialized item given in parseSelectionFile option by same parameter of above; used for manual item segmentation in ITERATIVE_PLAY_CONFIRM
    if nsArgParsed.parseSelectionFile!=None:
        deserializedItemsList=DeserializeSelectionSegments(open(nsArgParsed.parseSelectionFile).read())
        oldToGroupItems=list()
        for i in deserializedItemsList:     #filter eventual misformed deserialized old items
            if i.metadata!="" and i.pathName!="": oldToGroupItems.append(i)
        grouppingsOld=FlexibleGroupByFields(oldToGroupItems,groupByFields,excludeOnKeyList,excludeWildcard)
    ####### ORGANIZE GROUPS
    i=0
    itemsGroupped=list(grouppings.items())
    groupsTargets=list()
    itemsGroupped.sort(key=lambda x:len(x[1]))
    itemsGroupped.reverse()
    print(len(grouppings), len(itemsToGroup))
    ###LIST GROUPS
    for k,v in itemsGroupped:
        print("GRUOP ",i)
        print(k," --> ",len(v),"\n\n")
        for item in v:           print(i,"\tfile\t",item.nameID)
        groupsTargets.append(v)
        i+=1
    if nsArgParsed.genGroupFilenames!=0:   #build group filename listing if requested
        groupFileLinePrefix=nsArgParsed.genGroupFilenamesPrefix
        for i in range(len(itemsGroupped)):
            groupID,itemsList=itemsGroupped[i]
            if nsArgParsed.genGroupFilenameShuffle: shuffle(itemsList)
            outGroupFileName="group_"+str(i)+".list"
            file=open(outGroupFileName,"w")
            file.write("#"+str(groupID)+"\n")
            duration=0
            for item in itemsList:
                file.write("#startAtSec:\t"+str(duration)+"\tfor: "+str(item.duration)+"\n")
                file.write(groupFileLinePrefix+" "+item.pathName+"\n")
                duration+=item.duration
            file.close()
    if nsArgParsed.genGroupFilenames==2: exit(0)     #asked to exit after group file generation
    mostPopolousGroup,mostPopolousGroupKey=itemsGroupped[0][1],itemsGroupped[0][0]

    ### SELECT TARGET GROUPPABLE ITEMS
    if Take==GUI_GROUPS_SELECT:
        selection=guiMinimalStartGroupsMode(grouppings,trgtAction=SelectWholeGroup)
        groupsTargets=[selection]
    if Take==GUI_TUMBNAIL_GROUPS_SELECT:
        selection=guiMinimalStartGroupsMode(grouppings)
        print(selection)
        groupsTargets=[selection]
    elif Take==ITERATIVE_PLAY_CONFIRM :
        global SelectedGroupK
        if GUI_SELECT_GROUP_ITEMS:
            guiMinimalStartGroupsMode(grouppings,trgtAction=_select_items_group)    #invoke group gui selection with trgtAction: select the whole group
            trgtGroup=grouppings[SelectedGroupK]
            print("\n\n",trgtGroup,"\n\n")
        else:
            trgtGroup,SelectedGroupK=mostPopolousGroup,mostPopolousGroupKey

        # get old de serialized elements that are compatible with the selected group, if exists
        oldItemsGroup,oldItemsPathNames=None,None
        if SelectedGroupK in grouppingsOld:
            oldItemsGroup=grouppingsOld[SelectedGroupK]
            oldItemsPathNames=list()
            for i in oldItemsGroup: oldItemsPathNames.append(i.pathName)
        shuffle(trgtGroup)
        SelectedList,skipList=SelectItemPlay(trgtGroup,skipNameList=oldItemsPathNames,dfltStartPoint=segGenConfig["minStartConstr"],dfltEndPoint=segGenConfig["maxEndConstr"])  #list elements may contains both elem, [elem,[startSec,-1]],[elem,[-1,-1]] stupid..,[elem,[startSec,endSec]]
        if oldItemsGroup!=None: SelectedList.extend(oldItemsGroup)          #extend selection with the old de serialized one, if exist
        groupsTargets=[SelectedList]           #target groupsTargets setted to the single selected list
        printList(SelectedList)
        selectionSerialized=SerializeSelectionSegments(SelectedList,"selectionlist.json",append=True)
        skipListSerialized=SerializeSelectionSegments(skipList,"skiplist.json",append=True)
    else:
        SelectedList=mostPopolousGroup
        #SelectedList=metadataItems  #TODO force all
    #### SEGMENTIZE AND CONCAT SELECTED ITEMS GROUPPED BY BY BASH FFMPEG SCRIPT GENERATION
    shuffle(SelectedList)
    MAX_CONCAT=5000
    SelectedList=SelectedList[:MAX_CONCAT]

    for g in range(len(groupsTargets)):
        bash_batch_segs_gen,concat_filter_file,concat_filelist_fname = BASH_BATCH_SEGS_GEN+str(g),CONCAT_FILTER_FILE+str(g),CONCAT_FILELIST_FNAME+str(g)
        print(bash_batch_segs_gen,concat_filter_file,concat_filelist_fname)

        if nsArgParsed.justFFmpegConcatFilter:
            FFmpegConcatFilter(groupsTargets[g],concat_filter_file)
        else:
            FFmpegTrimConcatFlexible(groupsTargets[g],SEG_BUILD_METHOD=buildFFMPEG_segExtractNoReencode,segGenConfig=segGenConfig, \
                             BASH_BATCH_SEGS_GEN=bash_batch_segs_gen,CONCAT_FILELIST_FNAME=concat_filelist_fname,CONCAT_FILTER_FILE=concat_filter_file)
