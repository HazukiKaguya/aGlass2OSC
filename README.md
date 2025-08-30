# aGlass2OSC

## Intro
aGlass DK I/II Eye Tracker Eye Tracking Data OSC Sender For VRChat/VRCFT   
连接aGlassRuntime (Ver1.1.0.0)，调用API获取来自aGlass DK I/II Eye Tracker的原始眼动数据，并将其转换为VRC/VRCFT格式的眼动数据，然后使用OSC发送到VRChat。   

## Start
[aGlassRuntime](https://www.7invensun.com/filedownload/179638)   
Please make sure you have installed Python3.x,aGlassRuntime 1.1.0.0 then(PowerShell):   
请确保您安装了Python3.x和aGlassRuntime 1.1.0.0，然后输入(PowerShell):   
```PowerShell
pip install python-osc
```
Then download the .py file you need,use it(PowerShell).   
之后，下载您需要的.py文件，使用它(PowerShell)。   
For [VRChat](https://docs.vrchat.com/docs/osc-eye-tracking)
```PowerShell
python aGlass2vrc.py
```
For [VRCFT](https://docs.vrcft.io/docs/tutorial-avatars/tutorial-avatars-extras/parameters)
```PowerShell
python aGlass2vrcft.py
```

## Demo
https://private-user-images.githubusercontent.com/35645329/483859784-4a0a4789-5f76-45d8-946e-e2dfa3e044df.mp4
