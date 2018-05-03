#!/bin/bash


if [ -z "$2" ] ; then
  imbl4massive/initiate.sh $1
  cd $(basename $1) 
  ./proc.sh -t -c 100,0,100,0 -o 2,-381 1 
else

  cd $(basename $1) 
  ./proc.sh -d -c 70,0,70,0 -o 2,-381 -s $2 all

  rm -rf clean/SAMPLE_18*

  NS=$(ls clean/SAMPLE*0001*tif | cut -d '_' -f 3 | cut -d '.' -f 1)

  for curn in $NS ; do

    mkdir -p rec_$curn  

    sudo ~/flush_cash.sh

    xlictworkflow_local.sh \
      --indir $(realpath "clean") \
      --proj SAMPLE_\\d+_$curn.tif \
      --outdir  $(realpath "rec_$curn" ) \
      --file_prefix_ctrecon recon_.tif \
      --file_params params_ctworkflow.txt \
      --pixel_size 11.7 \
      --energy 80 \
      --angle_step 0.1 \
      --dark_correction 0 \
      --flat_correction 0 \
      --average_filter 1 \
      --zingers_filter 1 \
      --zingers_filter_size 9 \
      --zingers_filter_threshold 1.2 \
      --phase_extraction_pbi 0 \
      --phase_extraction_pbi_method 0 \
      --phase_extraction_delta_to_beta 50 \
      --phase_extraction_pbi_rprime 400000 \
      --ring_filter_sinogram 1 \
      --ring_filter_sinogram_size 17 \
      --recon_method 0 \
      --recon_filter 0 \
      --recon_out_mu 1 \
      --cor_method 2 \
      --recon_output_data_type 2 \
      --recon_out_scale 1 \
      --recon_scale_in_min 0 \
      --recon_scale_in_max 2 \
      --recon_out_scale_method 1
  done

fi
