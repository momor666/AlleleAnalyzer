#!/bin/bash
#$ -S /bin/bash
#$ -o /netapp/home/kathleen/ef_hg19_5kb/logs/
#$ -e /netapp/home/kathleen/ef_hg19_5kb/logs/
#$ -j y
#$ -cwd
#$ -l mem_free=4G
#$ -l arch=linux-x64
#$ -l netapp=1G,scratch=1G
#$ -l h_rt=336:00:00
#$ -t 1-25867
#$ -tc 500

export TMPDIR=/scratch
readarray all_genes < genes_hg19.txt
genes=(null ${all_genes[@]})
export gene=${genes[$SGE_TASK_ID]}
echo $SGE_TASK_ID
echo ${gene}

python ExcisionFinder_1kgp_hg19.py -v gene_list_hg37.tsv ${gene} /pollard/home/kathleen/projects/genome_surgery/1kgp_hg19/hg19_targs/ 10000 cpf1,SpCas9,SpCas9_VRER,SpCas9_EQR,SpCas9_VQR_1,SpCas9_VQR_2,StCas9,StCas9_2,SaCas9,SaCas9_KKH,nmCas9,cjCas9 /pollard/data/1kg/phase3/hg19/ ef_hg19_5kb/ --window=5000

qstat -j $JOB_ID
