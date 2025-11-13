clear
pn_in = 'C:\Users\brodricks\Documents\validation_team\projects\oregon\flatpack\camera_new_enclosure_3\camera_20percent\raw16';
pn_rois = 'C:\Users\brodricks\Documents\validation_team\projects\oregon\flatpack\camera_new_enclosure_3\camera_visible\raw16';
load(fullfile(pn_rois,'rois.mat'));
exp_times = 2.^(0:8).*500; % uints of microseconds
h = 3024; w = 4032;
file_number = 7;
fn = dir(fullfile(pn_in,['image_',num2str(exp_times(file_number)),'_16.raw']));
fid = fopen(fullfile(fn(1).folder,fn(1).name),'r');
img = fread(fid,[w,h],'uint16');
img = single(img');
fclose(fid);
figure(2)
clf
mn = median(img(:));
subplot(1,2,1)
imagesc(img,[mn*0.75,mn*[1.75]])
axis equal
width = 10;
for ii = 1 : length(hR)
    img(hR(ii)-width:hR(ii)+width -1,wR(ii)-width:wR(ii)+width -1 ) = 0;
end
subplot(1,2,2)
imagesc(img,[mn*0.75,mn*[1.25]])
axis equal

