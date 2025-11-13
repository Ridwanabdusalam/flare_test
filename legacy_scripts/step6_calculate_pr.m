clear
addpath('C:\Users\brodricks\Documents\MATLAB\myFunctions');
pn = 'C:\Users\brodricks\Documents\validation_team\projects\oregon\flatpack\camera_new_enclosure_4_cw';
pn_rois ='C:\Users\brodricks\Documents\validation_team\projects\oregon\flatpack\camera_new_enclosure_4_cw\camera_visible\raw16';
load(fullfile(pn_rois,'rois.mat'));
n_rois = length(hR);
scene = [10,15,20]; %PWM settings
scene_illumination = [587,855,933]; % illumination measured at camera location
nd_filter = 161/1503; % ratio with and without filter
reflectance = [0.915,0.597,0.363,0.196,0.0093,0.035];
exp_times = 2.^(0:8).*500; % uints of microseconds
n_exp = length(exp_times);
h = 3024; w = 4032;
n_d = length(scene);
sig = zeros(n_d,n_exp,n_rois);
width = 8;
for ii = 1 : n_d
    for ij = 1 : n_exp
        fn = dir(fullfile(pn,['camera_',num2str(scene(ii)),'percent'],'raw16',['image_',num2str(exp_times(ij)),'_16.raw']));
        img = read_raw(fn(1).folder,fn(1).name,h,w,'uint16');
        for ik = 1 : n_rois
            roi = img(hR(ik)-width:hR(ik)+width -1,wR(ik)-width:wR(ik)+width -1 );
            sig(ii,ij,ik) = mean2(roi);
        end
    end
end
% calculate photo-response
t = exp_times/1000;% convert to ms
pr = zeros(n_d,n_rois,2);
for ii = 1 : n_d
    for ij = 1 : n_rois
        line = squeeze(sig(ii,:,ij));
        bp = find(line>600);
        if(~isempty(bp))
            pr(ii,ij,:) = polyfit(t(1:bp(1)-1),line(1:bp(1)-1),1);
        else
            pr(ii,ij,:) = polyfit(t,line,1);
        end            
    end
end
% offset correct the data
sig_oc = sig;
for ii = 1 : n_d
    for ij = 1 : n_rois
        sig_oc(ii,:,ij) = sig(ii,:,ij) - squeeze(pr(ii,ij,2));
    end
end
% correct direct beam sig
sig(:,:,end) = sig(:,:,end)./nd_filter;


% plot results
clrs = {'*r','*g','*b','*c','*m','*k','*y','*r'};
clrs_fit = {'--r','--g','--b','--c','--m','--k','--y','--r'};
figure(1)
clf
subplot(2,2,1)
for ii = 1 : n_d
    for ij = 1 : 1
    loglog(t,squeeze(sig_oc(ii,:,end)),char(clrs(ij)))
    hold on
    yfit = polyval(squeeze(pr(ii,end,:)),t);
    loglog(t,yfit-squeeze(pr(ii,end,2)),char(clrs_fit(ij)))
    end
end

subplot(2,2,2)
for ii = 1 : n_d
    for ij = 1 : n_rois - 1
    loglog(t,squeeze(sig_oc(ii,:,ij)),char(clrs(ij)))
    hold on
    yfit = polyval(squeeze(pr(ii,ij,:)),t);
    loglog(t,yfit-squeeze(pr(ii,ij,2)),char(clrs_fit(ij)))
    end
end
pr_scene_illumination = zeros(n_rois,2);
subplot(2,2,3)
plot(scene_illumination,squeeze(pr(:,n_rois,1)),'*')
pr_scene_illumination(n_rois,:) = polyfit(scene_illumination,squeeze(pr(:,n_rois,1)),1);
yfit = polyval(pr_scene_illumination(n_rois,:),scene_illumination);
hold on
plot(scene_illumination,yfit,'--')

subplot(2,2,4)
for ii = 1 : n_rois - 2
    % plot(scene_illumination,squeeze(pr(:,ii,1)),'*')
    pr_scene_illumination(ii,:) = polyfit(scene_illumination,squeeze(pr(:,ii,1)),1);
    % yfit = polyval(pr_scene_illumination(ii,:),scene_illumination);
    % hold on
    % plot(scene_illumination,yfit,'--')
end
plot(reflectance,pr_scene_illumination(1:n_rois-2,1),'*')
pr_scene = polyfit(reflectance(2:n_rois-3),pr_scene_illumination(2:n_rois-3,1),1);
yfit = polyval(pr_scene,reflectance);
hold on
plot(reflectance,yfit,'--')

pr_scene_black_hole = polyfit(scene_illumination,squeeze(pr(:,n_rois-1,1)),1);
[1000*pr_scene(2),1000*pr_scene_black_hole(1)]


