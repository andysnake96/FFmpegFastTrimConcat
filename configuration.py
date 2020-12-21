#!/usr/bin/python3
# Copyright Andrea Di Iorio 2020
# This file is part of FFmpegFastTrimConcat
# FFmpegFastTrimConcat is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# FFmpegFastTrimConcat is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with FFmpegFastTrimConcat.  If not, see <http://www.gnu.org/licenses/>.

"""
Configuration module,
static configuration decladerd as global var UPERCASE_NAMED
dyn configuration handled by a dict (global CONF)
setted with vars' values in environ with the same name as key
"""

from os import environ as env

CONF=dict()   #ENVIRON CONFIGURATION VARNAME -> CONFIGURED VAL
isDictEntryT=lambda dictonary,key:    key in dictonary and dictonary[key]==True
def envConfig(cfg,varName,dflt=None):
    """ set in the dict cfg env[varName], if boolSet, convert to bool env value
        return  written value to varName
    """
    val=dflt
    if varName in env:
        val=env[varName]
        #cast the value accondingly to content
        if val.isdigit(): val=int(val)
        elif val.replace(".","").isdigit(): val=float(val)
        elif "TRUE" in val.upper(): val=True
        elif "FALSE" in val.upper():val=False

    #finally set the [casted] value
    cfg[varName]=val
    if isDictEntryT(cfg,"AUDIT_ENV_SET"): print("CONF[",varName,"]:",val,"\ttype:",type(val),"\tisDeflt:",val==dflt,sep="")
    return val

#concat groupping ffprobe's keys
""" GroupKeys, group items by common vals in these [wildcarded] metadata keys """
GroupKeys = ["width", "height", "sample_aspect_ratio"]
# groupKeys=["duration"]

""" ExcludeGroupKeys, group items by common vals in all metadatakeys but these [wildcarded]keys"""
ExcludeGroupKeys = ["duration", "bit_rate", "nb", "tag", "disposition", "has", "avg", "col", "refs", "index"]
# excludeGroupKeys=["bit_rate","nb_frames","tags","disposition","avg_frame_rate","color","index"]

##AUDIT
envConfig(CONF,"AUDIT_ENV_SET",True)
envConfig(CONF,"AUDIT_VIDINFO",True)
envConfig(CONF,"AUDIT_DSCPRINT",True)
envConfig(CONF,"AUDIT_MISSERR",True)
envConfig(CONF,"DEBUG",False)
envConfig(CONF,"QUIET",False)
if CONF["QUIET"]: #disable audits
    CONF["AUDIT_DSCPRINT"],CONF["AUDIT_MISSERR"],CONF["AUDIT_VIDINFO"]=False,False,False
    CONF["DEBUG"]=False


### DUMP - BACKUP
envConfig(CONF,"DUMP_ITEMS_FOUNDED",True)
ITEMS_LAST_FOUND="/tmp/lastItems.json"
TMP_SEL_FILE="/tmp/selection.tmp.list.json" #backup loc. IterativeTrimSelection at each select
SELECTION_LOGFILE="/tmp/selection"  #GUI selection file

JSON_INDENT=1	#json serialization file indentation

### INTERNAL CONFIGURATION
GIF_TUMBRL_EXTENSION = "gif"
IMG_TUMBRL_EXTENSION = "jpg"
VIDEO_MULTIMEDIA_EXTENSION = ["mp4", "wmw"]
METADATA_EXTENSION = "json"

REGEX_VID_SEGMENT=".*\.mp4\.[0-9]+\.mp4"
TMP_FULLVID_PATH_CUTS="/tmp/NO_FULLVIDEO.mp4"

##SCAN FOR VIDS
envConfig(CONF,"SAVE_GENERATED_METADATA",True) #save newly generated vids metadata
THRESHOLD_L_TO_HMAP=222 #thresh to convert a list to a dict in FilterItems(keepNIDS=WHITELIST_NAMEID)
envConfig(CONF,"OVERWR_FIELDS_NEMPTY",True) #merging items list:a,b, overwrite with a<-b with every nn epty field
#filtering
envConfig(CONF,"MIN_GROUP_DUR",6)
envConfig(CONF,"MIN_GROUP_LEN",6)
# pool workers
envConfig(CONF,"POOL_TRESHOLD",8)
envConfig(CONF,"POOL_SIZE",8)

##Trim
envConfig(CONF,"RADIUS_DFLT",1.596)


### GUI
envConfig(CONF,"PLAY_CMD","vlc")
envConfig(CONF,"DISABLE_GUI",False)
BTN_SELECTED_THICKNESS=4
BTN_NN_SELECTED_THICKNESS=1
envConfig(CONF,"GUI_COLSIZE",6)
lim=envConfig(CONF,"GUI_ITEMS_LIMIT",250)#max items 4 page (tkinter own limit~200)
lim-=lim%CONF["GUI_COLSIZE"]#end page with a full row
CONF["GUI_ITEMS_LIMIT"]=lim

THRESHOLD_KEY_PRINT=250  #max chars to show in a button
PLAY_SEGS_FIRST=True #if founded segments avail, play them before the full vid
PLAY_SELECTION_CUMULATIVE=True #if something selected, add to the play queue
#ITEMS'GRIDDED FRAME
SEG_TRIM_ENTRY_WIDTH=120
CANV_W,CANV_H=1900,1000
envConfig(CONF,"SCROLLBAR_W",18)
font = ("Arial", 15, "bold") #btn text font
#gif
envConfig(CONF,"MAX_FRAME_N",200)    #max gifs frame to considered 
#(too mutch frames for too mutch items per page && fewRAM avail => SIGTERM TODO OOMkiller?
envConfig(CONF,"GIF_UPDATE_POLL",96)
envConfig(CONF,"DRAW_GIF",True)
envConfig(CONF,"NameIdFirstDot",True)#extract nameID as pathname[:first dot]

DEFAULT_VID_INFOADD_STRING="ADD VID'S LABEL/INFOS"
#export comma separated list of keyword to filter away items after a scan
FilterKW=[]#["frame","out","fake","group_","?","clips"]
if env.get("FilterKW") != None: FilterKW=env["FilterKW"].split(",") 
envConfig(CONF,"FORCE_METADATA_GEN",True)# force the gen of metadata foreach vid

#### script configuration
MAX_CONCAT_DUR =float("inf")    #500
MAX_CONCAT_SIZE=float("inf")    #50 * 2 ** 20,
# ITERATIVE_TRIM_SELECT mode out filenames
SELECTION_FILE = "selection.list.json"
TRIM_RM_SCRIPT = "trimReencodingless.sh"
# CONCAT SEGS
CONCAT_FILELIST_FNAME="concat.list"
BASH_BATCH_SEGS_GEN="genSegs.sh"
CONCAT_FILTER_FILE="concat_filter_file.sh"
#ffmpeg configs
FFmpegNvidiaAwareDecode = " -vsync 0 -hwaccel cuvid -c:v h264_cuvid "
FFmpegNvidiaAwareEncode = " -c:v h264_nvenc -preset fast -coder vlc "
FFmpegDbg = " -hide_banner -y -loglevel 'error' "
FFmpegNvidiaAwareBuildPath = "/home/andysnake/ffmpeg/bin/nv/ffmpeg_g " + FFmpegDbg
FFmpegBasePath = "~/ffmpeg/bin/ffmpeg "

FFMPEG = FFmpegNvidiaAwareBuildPath
#TODO REMOVE
Encode = FFmpegNvidiaAwareEncode
Decode = FFmpegNvidiaAwareDecode
