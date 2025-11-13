clear
pn = 'C:\Users\brodricks\Documents\validation_team\projects\oregon\flatpack\camera_new_enclosure_4_cw\camera_visible\raw16';
exp_times = 2.^(0:8).*500; % uints of microseconds
h = 3024; w = 4032;
file_number = 9;
fn = dir(fullfile(pn,['image_',num2str(exp_times(file_number)),'_16.raw']));
fid = fopen(fullfile(fn(1).folder,fn(1).name),'r');
img = fread(fid,[w,h],'uint16');
img = single(img');
fclose(fid);
figure(1)
clf
imagesc(img)
axis equal
[wR,hR,~] = impixel();
save(fullfile(pn,'rois.mat'),'hR','wR')
width = 8;
for ii = 1 : length(hR)
    img(hR(ii)-width:hR(ii)+width -1,wR(ii)-width:wR(ii)+width -1 ) = 0;
end
figure(2)
clf
imagesc(img)
axis equal
saveas(2,fullfile(pn,'roi_check.png'))

