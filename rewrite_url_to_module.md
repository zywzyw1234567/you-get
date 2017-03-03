when the script is in the function calling stack is:
```
script_main
download_main
any_download
url_to_module
```
```download_main``` add non-flag input with http://
even an original URI begin with https://

the regex in the beginning of ```url_to_module``` won't help to guard it
for instance http://ahahahh/ will crash it (tested with version 0.4.652)
video_host gets ahahahh and video_url gets /
the script crash and print the calling stacks, nothing come to rescue



