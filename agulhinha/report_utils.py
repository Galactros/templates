def append_final_report_to_csv(csv_file, final_report_file_name):
    with open(final_report_file_name, "r") as final_report_f, open(csv_file, "a", newline='') as csv_f:
        csv_f.write("\nRelatorio Final:\n")
        csv_f.write(final_report_f.read())
