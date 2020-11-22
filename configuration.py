from os import environ as env


### DUMP
DUMP_ITEMS_FOUNDED=True                 #export
USE_DUMP_ITEMS_FOUNDED = True
ITEMS_LAST_FOUND="/tmp/lastItems.json"
JSON_INDENT=1	#json serialization file indentation

### INTERNAL CONFIGURATION PARAMS
# vid files handled extensions
GIF_TUMBRL_EXTENSION = "gif"
IMG_TUMBRL_EXTENSION = "jpg"
VIDEO_MULTIMEDIA_EXTENSION = ["mp4", "wmw"] #TODO NameIdFirstDot ?
METADATA_EXTENSION = "json"

##items scan
SAVE_GENERATED_METADATA=True #save newly generated vids metadata
if env.get("SAVE_GENERATED_METADATA") != None and "F" in env.get("SAVE_GENERATED_METADATA").upper():SAVE_GENERATED_METADATA=False
# pool workers
POOL_TRESHOLD = 100
if "POOL_TRESHOLD" in env: POOL_TRESHOLD = int(env["POOL_TRESHOLD"])
POOL_SIZE = 8
if "POOL_SIZE" in env: POOL_SIZE = int(env["POOL_SIZE"])

# var
MIN_GROUP_DUR=196
if "MIN_GROUP_DUR" in env: MIN_GROUP_DUR= int(env["MIN_GROUP_DUR"])
MIN_GROUP_LEN=6
if "MIN_GROUP_LEN" in env: MIN_GROUP_LEN= int(env["MIN_GROUP_LEN"])
PLAY_CMD=" vlc " #" mpv --hwdec=auto "
RADIUS_DFLT=1.596


##AUDIT
AUDIT_VIDINFO=True #__str__ , 
if "AUDIT_VIDINFO" in env and "F" in env["AUDIT_VIDINFO"].upper(): AUDIT_VIDINFO=False
AUDIT_DSCPRINT=False      #various print
if "AUDIT_DSCPRINT" in env and "T" in env["AUDIT_DSCPRINT"].upper(): AUDIT_DSCPRINT=True
AUDIT_MISSERR=True
if "AUDIT_MISSERR" in env and "F" in env["AUDIT_MISSERR"].upper():AUDIT_MISSERR=False
QUIET=False
if QUIET or "QUIET" in env and "F" in env["QUIET"].upper(): #disable audits
    QUIET,AUDIT_DSCPRINT,AUDIT_MISSERR,AUDIT_VIDINFO=True,False,False,False
    DEBUG=False
DEBUG=False
if "DEBUG" in env and "T" in env["DEBUG"].upper(): DEBUG=True
TMP_SEL_FILE="/tmp/selection.tmp.list.json" #backup loc. IterativeTrimSelection at each select


### GUI
DISABLE_GUI = False
SELECTION_LOGFILE="/tmp/selection"  #GUI selection file
if "DISABLE_GUI" in env and "T" in env["DISABLE_GUI"].upper(): DISABLE_GUI = True
BTN_SELECTED_THICKNESS=7
BTN_NN_SELECTED_THICKNESS=1
GUI_COLSIZE=5
if "GUI_COLSIZE" in env: GUI_COLSIZE=int(env["GUI_COLSIZE"])
GUI_ITEMS_LIMIT = 250   #tkinter's own limit on how mutch obj to display ...
THRESHOLD_KEY_PRINT=250  #max chars to show in a button
#ITEMS'GRIDDED FRAME
SEG_TRIM_ENTRY_WIDTH=120
CANV_W,CANV_H=1900,1000
SCROLLBAR_W=18    
font = ("Arial", 15, "bold") #btn text font
#gif
MAX_FRAME_N=20
GIF_UPDATE_POLL=96
DRAW_GIF=True   #if False, display just the tumbnails jpg if any
NameIdFirstDot = True# IF TRUE the nameID will be extracted from a path name up to the first founded dot
if env.get("NameIdFirstDot") != None and "F" in env["NameIdFirstDot"].upper(): NameIdFirstDot = False


#export comma separated list of keyword to filter away items after a scan
FilterKW=["frame","out","fake","group_","?","clips"]
if env.get("FilterKW") != None: FilterKW=env["FilterKW"].split(",") 
FORCE_METADATA_GEN = True  # force the generation of metadata of each founeded vid without a matching metadata file
if env.get("FORCE_METADATA_GEN") != None and "F" in env[
    "FORCE_METADATA_GEN"].upper(): FORCE_METADATA_GEN = False
#### script configuration
MAX_CONCAT_DUR =float("inf")    #500
MAX_CONCAT_SIZE=float("inf")    #50 * 2 ** 20,
# ITERATIVE_TRIM_SELECT mode out filenames
SELECTION_FILE = "selection.list.json"
TRIM_RM_SCRIPT = "trimReencodingless.sh"
### CONCAT SEGS
CONCAT_FILELIST_FNAME,BASH_BATCH_SEGS_GEN,CONCAT_FILTER_FILE=\
"concat.list","genSegs.sh","concat_filter_file.sh"


#### GROUP KEYS--------------------------
GroupKeys = ["width", "height", "sample_aspect_ratio"]
# groupKeys=["duration"]
# EXCLUDE KEYS-------------------------
# excludeGroupKeys=["bit_rate","nb_frames","tags","disposition","avg_frame_rate","color","index"]
ExcludeGroupKeys = ["duration", "bit_rate", "nb", "tag", "disposition", "has", "avg", "col", "refs", "index"]


PATH_SEP = ":"
FFmpegNvidiaAwareDecode = " -vsync 0 -hwaccel cuvid -c:v h264_cuvid "
FFmpegNvidiaAwareEncode = " -c:v h264_nvenc "
FFmpegNvidiaAwareEncode += " -preset fast -coder vlc "
FFmpegDbg = " -hide_banner -y -loglevel 'error' "
FFmpegNvidiaAwareBuildPath = "/home/andysnake/ffmpeg/bin/nv/ffmpeg_g " + FFmpegDbg
FFmpegBasePath = "~/ffmpeg/bin/ffmpeg "

FFMPEG = FFmpegNvidiaAwareBuildPath
### Env override config
Encode = FFmpegNvidiaAwareEncode
Decode = FFmpegNvidiaAwareDecode
if env.get("ENCODE") != None: Encode = env("ENCODE")
if env.get("DECODE") != None: Decode = env("DECODE")
if env.get("FFMPEG") != None: FFMPEG = env("FFMPEG")
