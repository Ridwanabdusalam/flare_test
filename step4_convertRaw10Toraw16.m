clear
pn = 'C:\Users\brodricks\Documents\validation_team\projects\oregon\flatpack\camera_new_enclosure_4_cw';
dn = dir(fullfile(pn,'camera_*'))
for ij = 1 : length(dn)
    pn_in = fullfile(dn(ij).folder,dn(ij).name)
    pn_out = fullfile(fullfile(pn_in,'raw16'));
    if ~exist(pn_out, 'dir')
    [~,~] = system(['mkdir ',fullfile(pn_in,'raw16')]);
    end
    
    h = 3024; w = 4032;
    
    fn= dir(fullfile(pn_in,'*.raw'));
    n_files = length(fn)
    for ii = 1 : n_files
        img = readRaw10(fn(ii).folder,fn(ii).name,pn_out,h,w);
    end
end

