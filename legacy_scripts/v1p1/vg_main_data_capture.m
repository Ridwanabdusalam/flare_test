% Veiling Glare main
% data capture sequence
% 1) Capture a set of images using the visible scene light source in the 
% enclosure of the light controller it is channel # 4
% 2) Capture a set of raw images. These images are store in folder camera
% 3) Rename folder to camera_visible
% 4) For three different VG incident illumination do the following
%   4.1) Set illumination level to 10 percent (channel # 0 on light controller
%   4.2) Capture a set of images (this is a longer set compared to the visible
%   light set)
%   4.2) rename the default folder (camera) to camera_[light level]

com_port = "COM11"; % comport for the light controller need to check using
% device manager that the com port is correct
s = serialport(com_port,19200);
configureTerminator(s,"CR");
flush(s);
pause(1.0);

% turn on internal lights
channel = 4; value = '010'; % value needs to be 3 digits is a percentage
writeline(s,['p 4 ', value])
capture_raw_visible_fn(); %  creates a foldr called camera with the images
% turn off internal lights
value = '000';
writeline(s,['p 4 ', value])
[a,b] = system('rename camera camera_visible');
light_level = {'010','015','020'};
for ii = 1 : 3
    writeline(s,['p 0 ', char(light_level(ii))])
    pause(1)
    capture_raw_fn();
    [a,b] = system(['rename camera camera_', char(light_level(ii))]);
    value = '000';
    writeline(s,['p 0 ', value])
    pause(0.5)
end

    

