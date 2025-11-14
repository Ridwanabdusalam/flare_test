function capture_raw_fn()
[a,b] = system("adb root");
pause(0.5);
[a,b] = system("adb shell setprop ctl.stop captureengineservice");
pause(0.5);
[a,b] = system("adb remount");
pause(0.5);
[a,b ] = system("adb shell rm -r /data/vendor/camera/*.jpg")
pause(0.5)
[a,b] = system("adb shell rm -r /data/vendor/camera/*.mp4")
pause(0.5)
[a,b] = system("adb shell rm -r /data/vendor/camera/*.raw")
pause(0.5)
%exp_times = 2.^(5:8).*1000 % uints of microseconds for visible
exp_times = 2.^(0:9).*500 % uints of microseconds
for ii = 1 : length(exp_times)
    [a,b] = system("adb shell rm -r /data/vendor/camera/*.raw")
    pause(0.5)
    [a,b] = system(['adb shell camcapture -c 0 -d 4032x3024 -e ' num2str(exp_times(ii)) ',1600 -r'])
    pause(0.5)
    [a,b] = system("adb pull /data/vendor/camera/")
    [a,b] = system(['rename camera\*.raw image_',num2str(exp_times(ii)),'.raw'])
    [a,b] = system('del camera\frame*.raw')
end

