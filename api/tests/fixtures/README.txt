Audio fixtures. All three are synthetic speech from the macOS `say` command
(voice Samantha), converted to AAC with `afconvert`. Nobody was recorded.

clip-short.m4a   4.4 s   used to warm the models and to test decoding
clip-demo.m4a   11 s     fed to the browser as a fake microphone when the demo GIF is recorded
clip-60s.m4a    60.9 s   the latency acceptance test; spoken at 140 words a minute with
                         0.7 s pauses between sentences to reach a full minute

The .txt next to each clip is the script that was spoken.

To regenerate one:
  sed -E 's/([.!?]) /\1 [[slnc 700]] /g' clip-60s.txt > /tmp/in.txt
  say -v Samantha -r 140 -o /tmp/clip.aiff -f /tmp/in.txt
  afconvert -f m4af -d aac -b 48000 -c 1 /tmp/clip.aiff clip-60s.m4a
