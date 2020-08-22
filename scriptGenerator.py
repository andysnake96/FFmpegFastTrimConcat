from collections import namedtuple
from random import shuffle

##TODO from MultimediaManagementSys import VidTuple
from configuraton import FFMPEG, Decode, Encode
#from MultimediaManagementSys import VidTuple
from utils import cleanPathname, parseTimeOffset

SegGenOptionsDflt = {"segsLenSecMin": None, "segsLenSecMax": None, "maxSegN": 1, "minStartConstr": 0,"maxEndConstr": None}

# python3 -c from MultimediaManagementSys import *; SegGenOptionsDflt['maxEndConstr']=-5;GenPlayIterativeScript(DeserializeSelectionSegments(open('selection.list').read()),outFilePath='selectionPlaySegs.sh')

def GenPlayIterativeScript(items, baseCmd="ffplay -autoexit ", segGenConfig=SegGenOptionsDflt, outFilePath=None):
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
                t = parseTimeOffset(end, True) - parseTimeOffset(s[0],True)  # compute end with duration from seeked start
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


# TODO ffmpeg any accurateSeek  + avoid_negative_ts make_zero -> initial null glitch
def GenTrimReencodinglessScriptFFmpeg(items, accurateSeek=False, outFname=None):
    """ generate a bash script to trim items by their embedded cutpoints
        video cut will be done with ffmpeg -ss -to -c copy (reencodingless video/audio out) -avoid_negative_ts 1 (ts back to 0 in cutted)
        video segements cutted will be written in the same path of source items with appended .1 .2 ... .numOfSegments
        if accurateSeek given True will be seeked as ffmpeg output option-> -i inFilePath before -ss,-to
        if outFname given, the script will be written in that path, otherwise printed to stdout

        outFnames written in subfolder of created dir cuts like cuts/itemNameID
    """
    outLines = list()
    outLines.append("mkdir cuts\n")
    outLines.append("FFMPEG=/home/andysnake/ffmpeg/bin/nv/ffmpeg_g  #set custom ffmpeg path here\n")
    for i in items:
        cutSubDir=" cuts/"+i.nameID+"/"
        outLines.append("mkdir '"+cutSubDir+"'\n")
        cutPointsNum = len(i.cutPoints)
        if cutPointsNum == 0: continue  # skip items without segments  -> no trimming required
        outLines.append("\n#SEGMENTS OF " + i.pathName + "\n")  
        outLines.append("\nmkdir cuts/" + i.nameID+ "\n")
        ffmpegInputPath = " -i '" + i.pathName+"' "
        # for each segments embedded generate ffmpeg -ss -to -c copy ...
        for s in range(cutPointsNum):
            seg = i.cutPoints[s]
            trimSegCmd = "eval $FFMPEG -loglevel error -hide_banner -n"
            if accurateSeek: trimSegCmd += ffmpegInputPath
            trimSegCmd += " -ss " + str(seg[0])
            if seg[1] != None: trimSegCmd += " -to " + str(seg[1])
            if not accurateSeek: trimSegCmd += ffmpegInputPath  # seek as output option
            # trimSegCmd+=" \t-c copy -avoid_negative_ts 1 "           #handle shifting of time stamps
            trimSegCmd += " -c copy -avoid_negative_ts make_zero "  # handle shifting of time stamps
            dstPath= "'"+cutSubDir+i.pathName.split("/")[-1]+ "." + str(s) + ".mp4'"  # progressive suffix for segments to generate
            trimSegCmd+=dstPath
            outLines.append(trimSegCmd + "\n")
        outLines.append("#rm " + i.pathName + "\n")  # commented remove cmd for currnt vid
    if outFname != None:
        fp = open(outFname, "w")
        fp.writelines(outLines)
        fp.close()
    else:
        print(outLines)

### SEG CUT CMD GEN
#RE-ENCODINGLESS
## cut a selected segment of video with seek options as input or output(more accurate ??)
buildFFMPEG_segExtractNoReencode=       lambda pathName,segStart,segTo,destPath:FFMPEG +" -ss " + str(segStart) +" -to " + str(segTo) +" -i '" + pathName +"' -c copy -avoid_negative_ts make_zero " + cleanPathname(destPath)
buildFFMPEG_segExtractPreciseNoReencode=lambda pathName,segStart,segTo,destPath:FFMPEG +" -i '" + pathName+"' -ss " + str(segStart) +" -to " + str(segTo)  +" -c copy -avoid_negative_ts make_zero " + cleanPathname(destPath)
#RE-ENCODING
buildFFMPEG_segTrimPreSeek=lambda pathName,segStart,segTo,destPath:FFMPEG+" -ss "+str(segStart)+" -i "+pathName+" -vf trim="+str(segStart)+":"+str(segTo)+Encode+"'"+destPath+"'" #trim filter
buildFFMPEG_segTrim=lambda pathName,segStart,segTo,destPath:FFMPEG+Decode+" -ss "+str(segStart)+" -i "+pathName+" -vf trim="+str(segStart)+":"+str(segTo)+Encode+"'"+destPath+"'" #trim filter
buildFFMPEG_segExtract_reencode=lambda pathName,segStart,segTo,destPath: FFMPEG+Decode+" -ss "+str(segStart)+" -to "+str(segTo)+" -i '"+pathName+"'"+Encode+"'"+destPath+"'"    #seek and re encode
##
##FFMPEG CONCAT DEMUXER
def FFmpegTrimConcatFlexible(itemsList,GenVideoCutSegmentsRndFunc, SEG_BUILD_METHOD=buildFFMPEG_segExtractNoReencode, segGenConfig=SegGenOptionsDflt,
                             **opts):
    """
        Cut segments from vids in itemsList then merge back via concatenation generating bash scripts
        basically the script will write generated segments in tmpCut/vidNameID/i.mp4  where i is in 0...n, n=# segs for vid
        @param itemsList:           vids to cut in segments, that segments will be concatenated togeter.
            cut segments will be generated with GenVideoCutSegmentsRnd
            if an item already have defined segs in its cutPoints field, them will be used to trim the vid
        @param GenVideoCutSegmentsRndFunc: function that take a Vid item and SegGenConfig to configure the random segment exrtaction from item
        @param SEG_BUILD_METHOD:    function used to gen the video segment in the BASH_BATCH_SEGS_GEN script
        @param segGenConfig:        segment generation configuration
        @param opts:  mode:         either CONCAT_DEMUXER, CONCAT_FILTER, ALL -> select concat modality
                      script names: BASH_BATCH_SEGS_GEN, CONCAT_FILELIST_FNAME,CONCAT_FILTER_FILE
                                -> respectivelly for cut script gen, concat demuxer list file, concatFilter script gen
                      var:          STORE_SEGMENTATION_INFO -> store rnd generated segments inside items
                                    CONCURERNCY_LEV_SEG_BUILD  -> level of concurrency used in trimming
    """
    # parse opts
    bash_batch_segs_gen,concatDemuxerList,concatFilter="segsBuild.sh","concat.list","concatFilter.sh"
    if opts.get("BASH_BATCH_SEGS_GEN") != None:         bash_batch_segs_gen = opts["BASH_BATCH_SEGS_GEN"]
    if opts.get("CONCAT_FILELIST_FNAME") != None:       concatDemuxerList = opts["CONCAT_FILELIST_FNAME"]
    if opts.get("CONCAT_FILTER_FILE") != None:          concatFilter= opts["CONCAT_FILTER_FILE"]
    storeSegmentationChoiced = False
    if opts.get("STORE_SEGMENTATION_INFO") != None:     storeSegmentationChoiced = opts["STORE_SEGMENTATION_INFO"]
    concurrencyLev=0
    if opts.get("CONCURERNCY_LEV_SEG_BUILD") != None: concurrencyLev= opts["CONCURERNCY_LEV_SEG_BUILD"]
    concatMode="CONCAT_DEMUXER"
    if opts.get("MODE") != None:    concatMode=opts["MODE"]
    assert concatMode in ["CONCAT_DEMUXER", "CONCAT_FILTER", "ALL"],"invalid concat mode given"
    ### SEG GEN
    TRAIL_CMD_SUFFIX = ""
    if concurrencyLev > 0: TRAIL_CMD_SUFFIX = " &"
    segInfoTup=namedtuple("segInfo","trgtPath trimCmd")          #info 1 segment
    itemTrimInfoTup=namedtuple("itemTrimInfo","vid segsDir segs")#info about an item with its segments (segs is a list of segInfoTup)
    itemsTrimList=list()
    for item in itemsList:
        assert not ( item.pathName == "" or item.sizeB == 0),"skip malformed itmes"
        #gen segs for vid item if not already defined in cutPoints field
        segs = item.cutPoints
        if len(segs)==0:        segs =  GenVideoCutSegmentsRndFunc(item, segGenConfig)
        if storeSegmentationChoiced:    item.cutPoints = segs  # store segments generated for current item
        trgtDir = "tmpCut/" + item.nameID
        segsInfos=list()
        for s in range(len(segs)):
            trgtSegDestPathName = trgtDir + "/" + str(s) + "." + item.extension #incresing num fname per segs
            start, to = segs[s][0], segs[s][1]
            assert int(start) in range(0,int(item.duration)+1) and int(to) in range(0,int(item.duration)+1),"invalid segments outside vid duration boundaries"
            ffmpegCutCmd= SEG_BUILD_METHOD(item.pathName, start, to, trgtSegDestPathName) + TRAIL_CMD_SUFFIX
            # interleave build cmd with wait to concurrency build fixed num of vids
            segsInfos.append(segInfoTup(trgtSegDestPathName,ffmpegCutCmd))
        itemsTrimList.append(itemTrimInfoTup(item,trgtDir,segsInfos))
    # write bash ffmpeg build segs
    bashBatchSegGen = open(bash_batch_segs_gen, "w")
    #preliminar cmds: tmp dir of tmpfs(optional), remove previous dir same named if any
    bashBatchSegGen.write("mkdir tmpCut\n#sudo mount -t tmpfs none tmpCut\n")
    bashBatchSegGen.write("#rm -r tmpCut/*\n")
    #directories for the segments to cut
    bashBatchSegGen.writelines(["mkdir "+item.segsDir+"\n" for item in itemsTrimList])
    #ffmpeg cut cmds
    segsCmds=[seg.trimCmd for item in itemsTrimList for seg in item.segs]   #extract trim cmds
    if concurrencyLev > 0:
        outCmds=list()
        for s in range(len(segsCmds)):
            outCmds.append(segsCmds[s]+"\n")
            if s%concurrencyLev == 0 and s>0: outCmds.append("wait\n")
    else:
        outCmds=[cmd+"\n" for cmd in segsCmds]
    bashBatchSegGen.writelines(outCmds)
    #write output segment file path list
    #extract segments file path adding ffmpeg concat demuxer list file suffix and prefixes
    segsFpathList=["file\t"+seg.trgtPath +"\n" for item in itemsTrimList for seg in item.segs]
    shuffle(segsFpathList)
    ### CONCAT
    if concatMode in ["ALL","CONCAT_DEMUXER"]:
        file = open(concatDemuxerList, "w")
        file.writelines(segsFpathList)
        file.close()
    elif concatMode in ["ALL","CONCAT_FILTER"]:
        segsItemsMock=[VidTuple(item.nameID,seg.trgtPath) for item in itemsTrimList for seg in item.segs]
        cmd=concatFilterCmd(segsItemsMock,ONTHEFLY_PIPE=False)
        file = open(concatFilter, "w")
        file.write(cmd)
        file.close()

##FFMPEG CONCAT FILTER
MULTILINE_OUT = True
def concatFilterCmd(items, outFname="/tmp/out.mp4", ONTHEFLY_PIPE=True, PIPE_FORMAT="matroska", HwDecoding=False):
    """
    generate ffmpeg concat filter cmd string, to concat the given items
    @param items: list of vids items to concat
    @param HwDecoding: flag to enable hw decoding on each vid
    optional output to a pipe to ffplay ( ffmpeg ... - | ffplay -) can be selected with ONTHEFLY_PIPE and PIPE_FORMAT
    """
    outStrCmd = FFMPEG
    inputsFiles = list()  # list of input lines
    numInputs = len(items)
    for i in items:
        itemLine = " -i '" + i.pathName + "'\t"
        inputsFiles.append(itemLine)
    shuffle(inputsFiles)  # shuf segment list as input operand
    prfx = "\\\n"
    if HwDecoding: prfx += Decode  # HW decoding for each input vid
    inputBlock = prfx + prfx.join(inputsFiles)
    outStrCmd += inputBlock + "\\\n"
    # gen concat filter streams string [1][2]..
    concatFilterInStreamsString = ""
    for x in range(numInputs): concatFilterInStreamsString += "[" + str(x) + "]"
    outStrCmd += ' -filter_complex "' + concatFilterInStreamsString + "concat=n=" + str(numInputs) + ':v=1:a=1"'
    outStrCmd += " -vsync 2"
    targetOutput = " " + outFname
    outStrCmd += Encode
    if ONTHEFLY_PIPE: targetOutput = " -f " + PIPE_FORMAT + " - | ffplay - "  # on the fly generate and play with ffplay
    outStrCmd += targetOutput
    return outStrCmd


def FFmpegConcatFilter(itemsList, outScriptFname, onTheFlayFFPlay=False, maxConcatSize=50 * 2 ** 20, maxConcatDur=500):
    """
    concat list of Vid items using the ffmpeg concat filter,
     considering subsets of elements with a max size/dur (pretty MEM intensive..)
     these subset of consecutive elements will be concatenated with in separate script
    @param itemsList:       list of Vid items to concat
    @param maxConcatSize:   max cumulative size of items to concat, elements in the order given in itemsList afther reached this threshold will be discarded
    @param maxConcatDur:    max cumulative duration of items to concat, elements in the order given in itemsList afther reached this threshold will be discarded
    @param outScriptFname:  output bash script name base name. will be created 1 script for each item's subset under the given thresholds
    @param onTheFlayFFPlay: concat output written to a pipe to ffplay
    """
    itemsPathsGroups = list()
    group = list()
    cumulativeSize, cumulativeDur = 0, 0
    for item in itemsList:
        # flush in single concat script items that have exceeded the thresholds
        if cumulativeDur + item.duration > maxConcatDur or cumulativeSize + item.sizeB > maxConcatSize:
            itemsPathsGroups.append(group)
            group = list()
        group.append(item)
    if len(group) > 0: itemsPathsGroups.append(group)   #add last group
    # for each group write a single concat filter script
    for i in range(len(itemsPathsGroups)):
        itemsPaths = itemsPathsGroups[i]
        outFp = open(outScriptFname + str(i), "w")
        ffmpegConcatFilterCmd = concatFilterCmd(itemsPaths, ONTHEFLY_PIPE=onTheFlayFFPlay,outFname="/tmp/out" + str(i) + outScriptFname + ".mp4")
        outFp.write(ffmpegConcatFilterCmd)
        outFp.close()



