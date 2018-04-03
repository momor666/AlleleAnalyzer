#!/usr/bin/env python3
# Rewriting `get_chr_tables.sh` in python
# -*- coding: utf-8 -*-
"""
get_chr_tables.py generates a table (tsv file) listing all variants in a defined interval for a specified 
individual (based on input VCF file). This basically reformats genotypes from VCF for easier 
processing later when designing sgRNAs.
Written in Python v 3.6.1.
Kathleen Keough and Michael Olvera 2017-2018.

Usage:
	get_chr_tables.py <vcf_file> <locus> <outdir> <name> [-f] [--bed]

Arguments:
	vcf_file           The sample vcf file, separated by chromosome. 
	locus			   Locus from which to pull variants, in format chromosome:start-stop, or a BED file, 
					   in which case you must specify --bed
	outdir             Directory in which to save the output files.
	name			   The name for the output file.
	-f                 If this option is specified, keeps homozygous variants in output file. 
	                   Therefore, downstream this will generate both allele-specific and non-
	                   allele-specific sgRNAs.
	--bed              Indicates that a BED file is being used in place of a locus.
"""
import pandas as pd
from docopt import docopt
import subprocess, os, sys
import regex as re

__version__='0.0.0'

REQUIRED_BCFTOOLS_VER = 1.5

def norm_chr(chrom_str, vcf_chrom):
	if vcf_chrom:
		return chrom_str.replace('chr','')
	elif not vcf_chrom:
		return('chr' + chrom_str)

def check_bcftools():
	""" 
	Checks bcftools version, and exits the program if the version is incorrect
	"""
	version = subprocess.run("bcftools -v | head -1 | cut -d ' ' -f2", shell=True,\
	 stdout=subprocess.PIPE).stdout.decode("utf-8").rstrip()
	if float(version) >= REQUIRED_BCFTOOLS_VER:
		print(f'bcftools version {version} running')

	else: 
		print(f"Error: bcftools must be >=1.5. Current version: {version}")
		exit()

def fix_multiallelics(cell):
	"""
	bcftools doesn't complete splitting of multiallelic variant sites.
	:param cell: genotype, str.
	:return: genotype as is if not multiallelic otherwise split multiallelic genotype, str.
	"""
	splitters = [',', ';']
	if any(splitter in str(cell) for splitter in splitters):
		cell = re.split(';|,', cell)[0]
	return cell


def het(genotype):
	gen1, gen2 = re.split('/|\|',genotype)
	return gen1 != gen2


def filter_hets(gens_df):
	"""
	filters for only heterozygous variants
	"""
	# print(gens_df.head(3))
	gens_df['het'] = gens_df.apply(lambda row: het(row['genotype']), axis=1)
	out = gens_df.query('het')[['chrom', 'pos', 'ref', 'alt', 'genotype']]
	return out


def main(args):
	print(args)
	# Make the outdir
	os.makedirs(args['<outdir>'], exist_ok=True)
	vcf_in = args['<vcf_file>']
	# Check if bcftools is installed, and then check version number
	check_bcftools()

	# if input is a BED file, run recursively
	if args['--bed']:
		bed_file = args['<locus>']
		print(f'Analyzing BED file {bed_file}')
		bed_df = pd.read_csv(bed_file, sep='\t', header=0, names=['chr','start','stop','locus'])
		hdf_out = pd.HDFStore(os.path.join(args['<outdir>'],args['<name>'] + '.h5'))
		for index, row in bed_df.iterrows():
			
			# check whether chromosome in VCF file includes "chr" in chromosome
			vcf_chrom = str(subprocess.Popen(f'gzcat {vcf_in} | tail -1 | cut -f1', shell=True))

			if vcf_chrom.startswith('chr'):
				chrstart = True
			else:
				chrstart = False

			# See if chrom contains chr
			chrom = str(row['chr'])
			start = row['start']
			stop = row['stop']

			# removes or adds "chr" based on analyzed VCF
			chr_name = norm_chr(chrom, chrstart)

			bcl_v=f"bcftools view -r {chr_name}:{str(start)}-{str(stop)} {args['<vcf_file>']}"
			
			# Pipe for bcftools
			bcl_view = subprocess.Popen(bcl_v,shell=True, stdout=subprocess.PIPE)
			bcl_norm = subprocess.Popen("bcftools norm -m -",shell=True, stdin=bcl_view.stdout, stdout=subprocess.PIPE)
			bcl_query = subprocess.Popen("bcftools query -f '%CHROM\t%POS\t%REF\t%ALT[\t%TGT]\n'",shell=True,
			 stdin=bcl_norm.stdout, stdout=subprocess.PIPE)
			bcl_query.wait() # Don't do anything else untill bcl_query is done running.

			# output  
			raw_dat = bcl_query.communicate()[0].decode("utf-8")

			temp_file_name=f"{args['<outdir>']}/{str(chrom)}_prechrtable.txt"
			with open(temp_file_name, 'w') as f:
				f.write(raw_dat)
				f.close()

			# Append fix_chr_tables.py
			vars = pd.read_csv(temp_file_name, sep='\t', header=None, names=['chrom', 'pos', 'ref', 'alt', 'genotype'],
				usecols=['chrom', 'pos', 'ref', 'alt', 'genotype'])

			if vars.empty and args['-f']:
				print('No variants in this region for this individual. Moving on.')
				os.remove(temp_file_name)
				continue
			elif vars.empty and not args['-f']:
				print('No heterozygous variants in this region for this individual. Moving on.')
				os.remove(temp_file_name)
				continue

			# this looks like it might be redundant now
			if 'chr' in str(vars.chrom.iloc[0]):
				vars['chrom'] = vars['chrom'].map(lambda x: norm_chr(x))

			if args['-f']:
				vars_fixed = vars.applymap(fix_multiallelics)
			else:
				vars_fixed = filter_hets(vars.applymap(fix_multiallelics))

			locus_name = {row['locus']}
			hdf_out.put(row['locus'],vars_fixed, format='t', data_columns=True, complib='blosc')
			print(f'{locus_name} done.')
			os.remove(temp_file_name)

	elif args['<locus>'].endswith('.bed') or args['<locus>'].endswith('.BED'):
		print('Must specify --bed if inputting a BED file. Exiting.')
		exit()
	else:
		print('Running single locus')

		# get locus info
		# check whether chromosome in VCF file includes "chr" in chromosome
		vcf_chrom = str(subprocess.Popen(f'gzcat {vcf_in} | tail -1 | cut -f1', shell=True))
		chrom = norm_chr(args['<locus>'].split(':')[0],vcf_chrom.startswith('chr'))
		start = args['<locus>'].split(':')[1].split('-')[0]
		stop = args['<locus>'].split(':')[1].split('-')[1]

		bcl_v=f"bcftools view -r {chrom}:{str(start)}-{str(stop)} {args['<vcf_file>']}"
		
		# Pipe for bcftools
		bcl_view = subprocess.Popen(bcl_v,shell=True, stdout=subprocess.PIPE)
		bcl_norm = subprocess.Popen("bcftools norm -m -",shell=True, stdin=bcl_view.stdout, stdout=subprocess.PIPE)
		bcl_query = subprocess.Popen("bcftools query -f '%CHROM\t%POS\t%REF\t%ALT[\t%TGT]\n'",shell=True,
		 stdin=bcl_norm.stdout, stdout=subprocess.PIPE)
		bcl_query.wait() # Don't do anything else untill bcl_query is done running.

		# output  
		raw_dat = bcl_query.communicate()[0].decode("utf-8")

		temp_file_name=f"{args['<outdir>']}/{str(chrom)}_prechrtable.txt"
		with open(temp_file_name, 'w') as f:
			f.write(raw_dat)
			f.close()

		# Append fix_chr_tables.py
		vars = pd.read_csv(temp_file_name, sep='\t', header=None, names=['chrom', 'pos', 'ref', 'alt', 'genotype'],
			usecols=['chrom', 'pos', 'ref', 'alt', 'genotype'])

		if vars.empty and args['-f']:
			print('No variants in this region for this individual. Exiting.')
			exit()
		elif vars.empty and not args['-f']:
			print('No heterozygous variants in this region for this individual. Exiting.')
			exit()

		if args['-f']:
			vars_fixed = vars.applymap(fix_multiallelics)
		else:
			vars_fixed = filter_hets(vars.applymap(fix_multiallelics))

		if args['<name>']:
			outname = f"{args['<name>']}.hdf5"
		else:
			outname = f'chr{chrom}_gens.hdf5'

		vars_fixed.to_hdf(os.path.join(args['<outdir>'], outname), 'all', format='t', data_columns=True, complib='blosc')

		os.remove(temp_file_name)


if __name__ == '__main__':
	arguments = docopt(__doc__, version='0.1')
	main(arguments)
