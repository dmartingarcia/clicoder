#!/bin/sh
set -eu
. /work/montaje.env
OUT="/videos/$NN.mp4"
IN="/clips/$NN.webm"
VW=1632; VH=962; BAR=44; CW=1632; CH=918
OUTST=$(awk "BEGIN{printf \"%.3f\", $DCE-0.7}")
LIM=$(awk "BEGIN{printf \"%.3f\", $DCE+1}")
FIN_V=$(awk "BEGIN{printf \"%.3f\", $TOTAL-0.7}")
FIN_A=$(awk "BEGIN{printf \"%.3f\", $TOTAL-3}")

SEQ="fps=30,scale=1920:1080:flags=bicubic,noise=alls=4:allf=t,format=yuv420p,setsar=1,settb=AVTB,setpts=PTS-STARTPTS"

STATS=-nostats; [ "${FFLOG:-error}" = error ] || STATS=-stats
set -- -hide_banner -filter_complex_threads 1 -loglevel "${FFLOG:-error}" $STATS -y \
  -framerate 30 -i /work/intro/%04d.jpg \
  -i "$IN" \
  -framerate 30 -i /work/cierre/%04d.jpg
NIN=3
VFC="[0:v]$SEQ[intro];[2:v]$SEQ[outro];"
CLIPFIT="trim=start=$TRIM,setpts=(PTS-STARTPTS)/$VEL,fps=30"
PNGLOOP="loop=loop=-1:size=1,setpts=N/(30*TB),trim=duration=$LIM"

if [ "$MARCO" = 1 ]; then
  set -- "$@" \
    -framerate 30 -i /work/malla/%04d.jpg \
    -i /work/ventana/sombra.png \
    -i /work/ventana/fondo.png \
    -i /work/ventana/mascara.png \
    -i /work/ventana/reflejo.png
  NIN=8
  F="(0.93+0.07*(1-pow(1-min(1,max(0,t-0.2)/0.9),3)))*(1+0.05*pow(max(0,min(1,(t-$OUTST)/0.7)),2))"
  VFC="$VFC
 [3:v]loop=loop=-1:size=240,setpts=N/(30*TB),trim=duration=$LIM,scale=1920:1080:flags=bicubic,noise=alls=4:allf=t,format=yuv420p,setsar=1[bg];
 [1:v]$CLIPFIT,scale=$CW:$CH:force_original_aspect_ratio=decrease,pad=$CW:$CH:(ow-iw)/2:(oh-ih)/2:color=$CF,setsar=1,format=yuv420p[clip];
 [6:v]$PNGLOOP,format=gray,scale=$CW:$CH[mask];
 [clip][mask]alphamerge[clipa];
 [5:v]$PNGLOOP,format=rgba[win];
 [win][clipa]overlay=0:$BAR:format=auto:shortest=1[w0];
 [7:v]$PNGLOOP,format=rgba[refl];
 [w0][refl]overlay=0:0:format=auto:shortest=1,format=rgba,fade=t=in:st=0.25:d=0.7:alpha=1,fade=t=out:st=$OUTST:d=0.6:alpha=1[w2];
 [w2]scale=w='trunc($VW*($F))':h='trunc($VH*($F))':eval=frame:flags=bicubic[w3];
 [4:v]$PNGLOOP,format=rgba,fade=t=in:st=0.25:d=0.7:alpha=1,fade=t=out:st=$OUTST:d=0.6:alpha=1[sombra];
 [bg][sombra]overlay=0:0:format=auto:shortest=1[m0];
 [m0][w3]overlay=x='(main_w-overlay_w)/2':y='(main_h-overlay_h)/2':eval=frame:format=auto:shortest=1[m1];"
  ULT=m1
  if [ "$PROGRESO" = 1 ]; then
    set -- "$@" -f lavfi -i "color=c=white:s=1920x6:r=30:d=$LIM,format=rgba,colorchannelmixer=aa=0.14" \
                -f lavfi -i "gradients=s=1920x6:c0=$CA:c1=$CACC:x0=0:y0=0:x1=1920:y1=0:speed=0.0001:r=30:d=$LIM"
    PT=$NIN; PB=$((NIN + 1)); NIN=$((NIN + 2))
    VFC="$VFC
 [m1][$PT:v]overlay=0:1064:format=auto:shortest=1[m2];
 [m2][$PB:v]overlay=x='-overlay_w+overlay_w*t/$DCE':y=1064:eval=frame:format=auto:shortest=1[m3];"
    ULT=m3
  fi
  VFC="$VFC
 [$ULT]trim=duration=$DCE,setpts=PTS-STARTPTS,fps=30,format=yuv420p,setsar=1,settb=AVTB[main];"
else
  VFC="$VFC
 [1:v]$CLIPFIT,scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=$CF,setsar=1,format=yuv420p,settb=AVTB,setpts=PTS-STARTPTS[main];"
fi

VFC="$VFC
 [intro][main]xfade=transition=fade:duration=$XF:offset=$OFF1[a];
 [a][outro]xfade=transition=fade:duration=$XF:offset=$OFF2[b];
 [b]fade=t=out:st=$FIN_V:d=0.7,format=yuv420p[v]"

if [ "$MUSICA" = 1 ] && [ -f /work/musica.wav ]; then
  set -- "$@" -i /work/musica.wav
  AI=$NIN
  FACT=$(awk "BEGIN{printf \"%.4f\", $MVOL/0.10}")
  FC="$VFC;
 [$AI:a]atrim=0:$TOTAL,asetpts=PTS-STARTPTS,loudnorm=I=-17.5:TP=-1.5:LRA=9,aresample=48000,afade=t=in:st=0:d=1.5,afade=t=out:st=$FIN_A:d=3,volume=$FACT,alimiter=limit=0.89[aud]"
  set -- "$@" -filter_complex "$FC" -map "[v]" -map "[aud]" -c:a aac -b:a 192k -ar 48000
else
  set -- "$@" -filter_complex "$VFC" -map "[v]" -an
fi
TMP="/tmp/montaje_$NN.mp4"
set -- "$@" -t "$TOTAL" -c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p -r 30 -movflags +faststart "$TMP"
ffmpeg "$@"
cp "$TMP" "$OUT"

D=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT")
echo "$NN: $OUT (${D}s)"
awk "BEGIN{ if ($D<75 || $D>105) print \"  dura \" $D \" s, fuera de 75-105 s\" }"
