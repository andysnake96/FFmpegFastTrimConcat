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

from collections import namedtuple
from random import shuffle

##TODO from MultimediaManagementSys import VidTuple
from configuration import *
from utils import cleanPathname, parseTimeOffset
SegGenOptionsDflt = {"segsLenSecMin": None, "segsLenSecMax": None, "maxSegN": 1,
     "minStartConstr": 0,"maxEndConstr": None}

# python3 -c from MultimediaManagementSys import *; SegGenOptionsDflt['maxEndConstr']=-5;GenPlayIterativeScript(DeserializeSelectionSegments(open('selection.list').read()),outFilePath='selectionPlaySegs.sh')

def GenPlayIterativeScript(items, baseCmd="ffplay -autoexit ",
    segGenConfig=SegGenOptionsDflt, outFilePath=None):
    """generate a bash script to play all items selected segments
       if no segmenet embedded inside Vid -> play the whole video
       UC review a serialized selection file
    """
    outLines = list()
    j = 0
    ##startConstr=segGenConfig["minStartConstr"]    #TODO?
    ##endConstr=segGenConfig["maxEndConstr"]
    for i in items:
        if i.cutPoints != list():
            for s in i.cutPoints:
                playCmd = baseCmd
                playCmd += " -ss " + str(s[0])
                # set segEndTime default overridable by nn None seg end
                end = i.duration
                if s[1] != None: end = s[1]
                # if end<=0:end+=i.duration
                print(end, s[0], "\n")
                # compute end with duration from seeked start
                t = parseTimeOffset(end, True) - parseTimeOffset(s[0],True)  
                playCmd += " -t " + str(t)
                playCmd += " -window_title '" + str(j) + "  " + i.nameID + "'"
                playCmd += " '" + i.pathName + "'\n"
                outLines.append(playCmd)
                j += 1
        else:  # no segs defined for current item
            playCmd = baseCmd + " -window_title " + str(j) + " '" + i.pathName + "'\n"
            outLines.append(playCmd)
            j += 1

    if outFilePath != None:
        fp = open(outFilePath, "w")
        fp.writelines(outLines)
        fp.close()
    else:
        print(outLines)
    return outLines


def GenTrimReencodinglessScriptFFmpeg(items, accurateSeek=False, outFname=None,
    dstCutDir="cuts"):
    """ 
        generate a bash script to trim items by their embedded cutpoints
        video cut will be done with ffmpeg -ss -to -c copy -avoid_negative_ts 1
        (reencodingless video/audio out + ts back to 0 in cutted)
        video segements cutted will be written like in ..dstCutDir/itemNameID/.1.mp4 ...
        with appended .1 .2 ... .numOfSegments
        @param accurateSeek: if True will be seeked as ffmpeg output option
            (-i inFilePath -ss -to instead of -ss -to -i inFilePath )
        @param outFname: if True, the generated script will be written in that path, 
        @param dstCutDir: path of trimmed segments
        @Returns:   script as a string
    """
    #clean dstCutDir
    dstCutDir=dstCutDir.strip()
    if dstCutDir[-1]=="/": dstCutDir=dstCutDir[:-1]

    outLines = list()
    outLines.append("mkdir "+dstCutDir+" \n")
    outLines.append("FFMPEG=/home/andysnake/ffmpeg/bin/nv/ffmpeg_g #custom ffmpeg\n")
    outLines.append("FFMPEG+=\"-loglevel error -hide_banner -n\"")
    for i in items:
        cutSubDir=dstCutDir+"/"+i.nameID+"/"
        outLines.append("mkdir '"+cutSubDir+"'\n")
        cutPointsNum = len(i.cutPoints)
        if cutPointsNum == 0: continue 

        outLines.append("\n#SEGMENTS OF " + i.pathName +" \t"+ str(i.duration/60)+"mins \n")  
        ffmpegInputPath = " -i '" + i.pathName+"' "
        # for each segments embedded generate ffmpeg -ss -to -c copy ...
        for s in range(cutPointsNum):
            seg = i.cutPoints[s]
            trimSegCmd = "eval $FFMPEG "
            if accurateSeek: trimSegCmd += ffmpegInputPath     #seek as output opt
            trimSegCmd += " -ss " + str(seg[0])
            if seg[1] != None: trimSegCmd += " -to " + str(seg[1])
            if not accurateSeek: trimSegCmd += ffmpegInputPath #seek as input opt
            trimSegCmd += " -c copy -avoid_negative_ts make_zero " #shift ts
            #name seg file with progressive suffix
            dstPath= " '"+cutSubDir+i.pathName.split("/")[-1]+ "." + str(s) + ".mp4'"  
            trimSegCmd+=dstPath
            outLines.append(trimSegCmd + "\n")
        outLines.append("#rm " + i.pathName + "\n"+"#"*22+"\n")  # commented remove cmd for currnt vid

    if outFname != None:
        fp = open(outFname, "a")
        fp.writelines(outLines)
        fp.close()
    
    return "\n".join(outLines)

### SEG CUT CMD GEN
#RE-ENCODINGLESS
## cut a selected segment of video with seek options as input or output(more accurate ??)
buildFFMPEG_segExtractNoReencode=lambda pathName,segStart,segTo,destPath:"eval $FFMPEG" +" -ss " + str(segStart) +" -to " + str(segTo) +" -i '" + pathName +"' -c copy -avoid_negative_ts make_zero " + cleanPathname(destPath)
buildFFMPEG_segExtractPreciseNoReencode=lambda pathName,segStart,segTo,destPath:"eval $FFMPEG" +" -i '" + pathName+"' -ss " + str(segStart) +" -to " + str(segTo)  +" -c copy -avoid_negative_ts make_zero " + cleanPathname(destPath)
#RE-ENCODING
buildFFMPEG_segTrimPreSeek=lambda pathName,segStart,segTo,destPath:FFMPEG+" -ss "+str(segStart)+" -i "+pathName+" -vf trim="+str(segStart)+":"+str(segTo)+Encode+"'"+destPath+"'" #trim filter
buildFFMPEG_segTrim=lambda pathName,segStart,segTo,destPath:FFMPEG+Decode+" -ss "+str(segStart)+" -i "+pathName+" -vf trim="+str(segStart)+":"+str(segTo)+Encode+"'"+destPath+"'" #trim filter
buildFFMPEG_segExtract_reencode=lambda pathName,segStart,segTo,destPath: FFMPEG+Decode+" -ss "+str(segStart)+" -to "+str(segTo)+" -i '"+pathName+"'"+Encode+"'"+destPath+"'"    #seek and re encode
##
##FFMPEG CONCAT DEMUXER
def FFmpegTrimConcatFlexible(itemsList,SEG_BUILD_METHOD=buildFFMPEG_segExtractNoReencode, 
    segGenConfig=SegGenOptionsDflt,**opts):
    """
    Cut segments from vids in itemsList 
    then merge back via concatenation generating bash scripts
    basically the script will write generated segments in tmpCut/vidNameID/i.mp4 
    where i is in 0...n, n=# segs for vid

    @param itemsList:  vids to cut in segments, if an item already have 
        defined segs in its cutPoints field, them will be used to trim the vid
    @param GenVideoSegRndFunc: 
        func such that Vid,SegGenConfig -> segment specification for the vid
    @param SEG_BUILD_METHOD: func used to gen the video segment in the script
    @param segGenConfig: segment generation configuration
    @param opts:  
     script names: BASH_BATCH_SEGS_GEN, CONCAT_FILELIST_FNAME,CONCAT_FILTER_FILE
      (respectivelly for cut script gen, concat demuxer list file,
      concatFilter script gen)
     var:  CONCURERNCY_LEV_SEG_BUILD-> ammount of concurrent ffmpeg trim cmds
    """
    if DEBUG: print(segGenConfig,opts,SEG_BUILD_METHOD)
    # parse opts
    bash_batch_segs_gen,concatDemuxerList,concatFilter=\
    "segsBuild.sh","concat.list","concatFilter.sh"
    if opts.get("BASH_BATCH_SEGS_GEN")!=None:
        bash_batch_segs_gen = opts["BASH_BATCH_SEGS_GEN"]
    if opts.get("CONCAT_FILELIST_FNAME")!=None:
        concatDemuxerList = opts["CONCAT_FILELIST_FNAME"]
    if opts.get("CONCAT_FILTER_FILE")!=None:
        concatFilter= opts["CONCAT_FILTER_FILE"]
    concurrencyLev=0
    if opts.get("CONCURERNCY_LEV_SEG_BUILD")!=None:
        concurrencyLev= int(opts["CONCURERNCY_LEV_SEG_BUILD"])

    ### SEG GEN
    TRAIL= ""
    if concurrencyLev > 0: TRAIL= " &"
    segInfoTup=namedtuple("segInfo","trgtPath trimCmd")          #segment
    itemTrimInfoTup=namedtuple("itemTrimInfo","vid segsDir segs")#item+list of segInfoTup
    itemsTrimList=list()
    for item in itemsList:
        assert not ( item.pathName == "" or item.sizeB == 0 ),"malformed itme"

        segs = item.cutPoints
        if len(segs)==0:        
            segs=segGenConfig["genSegFunc"](item, segGenConfig)
            item.cutPoints = segs 

        trgtDir = "tmpCut/" + item.nameID
        segsInfos=list()
        for s in range(len(segs)):
            start, to = segs[s][0], segs[s][1]

            assert int(start) in range(0,int(item.duration)+1) and \
             int(to) in range(0,int(item.duration)+1),"seg outside len boundaries"

            dstSegPath = trgtDir + "/" + str(s) + "." + item.extension 
            ffmpegCutCmd=SEG_BUILD_METHOD(item.pathName, start, to, dstSegPath)+TRAIL
            if DEBUG: print(ffmpegCutCmd)
            segsInfos.append(segInfoTup(dstSegPath,ffmpegCutCmd))#add seg
    
        itemsTrimList.append(itemTrimInfoTup(item,trgtDir,segsInfos))#add item+segs

    # write bash ffmpeg build segs
    bashBatchSegGen = open(bash_batch_segs_gen, "w")
    #preliminar cmds: tmp dir of tmpfs(optional), remove previous dir same named if any
    bashBatchSegGen.write("export FFMPEG=\""+FFMPEG+
        "\"\nmkdir tmpCut\n#sudo mount -t tmpfs none tmpCut o size=6G,noatime\n")
    bashBatchSegGen.write("#rm -r tmpCut/*\n")
    #directories for the segments to cut
    bashBatchSegGen.writelines(["mkdir '"+item.segsDir+"'\n" for item in itemsTrimList])
    #ffmpeg cut cmds
    segsCmds=[seg.trimCmd for item in itemsTrimList for seg in item.segs]   #extract trim cmds
    if concurrencyLev > 0:
        outCmds=list()
        for s in range(len(segsCmds)):  
            outCmds.append(segsCmds[s]+"\n")
            if s%concurrencyLev == 0 and s>0: outCmds.append("wait\n")
        if len(segsCmds)-1 % concurrencyLev != 0: outCmds.append("wait \n") #wait last segs
    else:
        outCmds=[cmd+"\n" for cmd in segsCmds]
    bashBatchSegGen.writelines(outCmds)
    #write output segment file path list
    #extract segments file path adding ffmpeg concat demuxer list file suffix and prefixes
    segsFpathList=["file\t"+seg.trgtPath +"\n" for item in itemsTrimList for seg in item.segs]
    shuffle(segsFpathList)
    ### CONCAT
    file = open(concatDemuxerList, "w")
    file.writelines(segsFpathList)
    file.close()

##FFMPEG CONCAT FILTER
MULTILINE_OUT = True
def concatFilterCmd(items, outFname="/tmp/out.mp4", onthefly_pipe=True,
    PIPE_FORMAT="matroska", HwDecoding=False):
    """
    generate ffmpeg concat filter cmd string, to concat the given items
    each item will be cutted accordingly to its cutPoints field (if not empty)
    @param items: list of vids items to concat
    @param HwDecoding: flag to enable hw decoding on each vid
    @param onthefly_pipe: output to a pipe to ffplay ( ffmpeg ... - | ffplay -) 
        PIPE_FORMAT has to be a container format that support pipe output
    """
    outStrCmd = FFMPEG
    inputsFiles = list()  # list of input lines
    for i in items:
        itemLine = " -i '" + i.pathName +"' \t"
        #add cut points (if any)
        segs=i.cutPoints
        for s in segs:
            inputsFiles.append("\t -ss "+str(s[0])+"\t -to "+str(s[1])+itemLine)
        #check if not added any input yet
        if len(segs)==0:    inputsFiles.append(itemLine)
    prfx = "\\\n"
    if HwDecoding: prfx += Decode  # HW decoding for each input vid
    outStrCmd += prfx + prfx.join(inputsFiles) + "\\\n"
    # gen concat filter streams string [1][2]..
    concatFStreamsStr = ""
    for x in range(len(items)): concatFStreamsStr+= "[" + str(x) + "]"
    outStrCmd += ' -filter_complex "' + concatFStreamsStr+\
         "concat=n=" + str(len(items)) + ':v=1:a=1"'
    outStrCmd += " -vsync 2"
    targetOutput = " " + outFname
    outStrCmd += Encode
    if onthefly_pipe: targetOutput = " -f " + PIPE_FORMAT + " - | ffplay - "
    outStrCmd += targetOutput
    return outStrCmd


def FFmpegConcatFilter(itemsList, outScriptFname, segGenConfig=None,
    onTheFlayFFPlay=False,maxConcatSize=MAX_CONCAT_SIZE, maxConcatDur=MAX_CONCAT_DUR):
    """
    concat list of Vid items using the ffmpeg concat filter,
     considering subsets of elements with a max size/dur (pretty MEM intensive..)
     these subset will be concatenated with in separate script.
     if items given own some cutPoints, will be prefixed ffmpeg'sinput option

    @param itemsList:       list of Vid items to concat
    @param maxConcatSize:   max cumulative size of items to concat, 
        elements in the order given in itemsList afther reached this threshold
        will be discarded
    @param segGenConfig:    segment generation config (constraints +genFunc)
        if not None, segs will be generated for each item 
    @param maxConcatDur:    max cumulative duration of items to concat, 
        elements in the order given in itemsList afther reached this threshold 
        will be discarded
    @param outScriptFname:  output bash script name base name. will be created 
        1 script for each item's subset under the given thresholds
    @param onTheFlayFFPlay: concat output written to a pipe to ffplay
    """
    itemsPathsGroups = list()
    group = list()
    cumulativeSize, cumulativeDur = 0, 0
    for item in itemsList:
        # flush in single concat script items that have exceeded the thresholds
        if cumulativeDur + item.duration > maxConcatDur or\
            cumulativeSize + item.sizeB > maxConcatSize:
            itemsPathsGroups.append(group)
            group = list()
        if segGenConfig!=None and len(item.cutPoints)==0: #gen seg if required
            item.cutPoints=segGenConfig["genSegFunc"](item,segGenConfig)
        group.append(item)
    if len(group) > 0: itemsPathsGroups.append(group)   #add last group

    # for each group write a single concat filter script
    for i in range(len(itemsPathsGroups)):
        nameSuffix=str(i)
        if i==0: nameSuffix=""

        itemsPaths = itemsPathsGroups[i]
        outFp = open(outScriptFname + nameSuffix, "w")
        ffmpegConcatFilterCmd = concatFilterCmd(itemsPaths, outFname="/tmp/out"
            + nameSuffix + outScriptFname + ".mp4",onthefly_pipe=onTheFlayFFPlay,)
        outFp.write(ffmpegConcatFilterCmd)
        outFp.close()



if __name__=="__main__":
    ## FULL COVERAGE AUTO FUNCS CALL
    import sys
    thismodule = sys.modules[__name__]
    emptyF=lambda x:x
    print("module attributes")
    for x in dir(): print(x,type(getattr(thismodule,x)))
    print("calling all functions")
    functions=[getattr(thismodule,x) for x in dir() if type(getattr(thismodule,x)) == type(emptyF)]
    for f in functions: 
        try: f()
        except: print()
