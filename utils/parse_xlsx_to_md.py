import pandas as pd
import argparse
import os

parser = argparse.ArgumentParser()
parser.add_argument("--path","-P",type=str, required=True)
parser.add_argument("--name","-N",type=str, default="services_from_xl.md")
parser.add_argument("--header","-H",type=int, default=2)
args = parser.parse_args()

xl_df = pd.read_excel(args.path, header=args.header)

with open(args.name, "a", encoding='utf-8') as file:
    for _, row in xl_df.iterrows():

        content = f"# **Service page:** **code:** {row.iloc[0]}, **name:** {row.iloc[1]}\n## The service description:\n{row.iloc[4] if row.iloc[4]!=None else '' }\n## Key words:\n {row.iloc[3] if row.iloc[3]!=None else ''}\n## Examples of questions that can relate to this service:\n{row.iloc[5] if row.iloc[5]!=None else ''}"
        metadata_code = row.iloc[0]
        metadata_name = row.iloc[1]

        file.write(content + "\n")

#python parse_xlsx_to_md.py --path services.xlsx --name output.md --header 1
