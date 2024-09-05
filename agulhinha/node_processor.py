from command_utils import run_command

def process_nodes(cluster, csv_writer, final_report_file):
    print(f"Processando informacoes dos nodes para o cluster: {cluster}")
    
    run_command(f"oc config use-context {cluster}")
    node_list = run_command("oc adm top nodes --no-headers --use-protocol-buffers")
    
    for line in node_list.splitlines():
        node_data = line.split()
        node_name = node_data[0]
        node_cpu_usage = node_data[1]
        node_cpu_percent = node_data[2]
        node_memory_usage = node_data[3]
        node_memory_percent = node_data[4]

        if int(node_cpu_percent.strip('%')) >= 80 or int(node_memory_percent.strip('%')) >= 80:
            final_report_file.write(f"{cluster}|{node_name} -> CPU: {node_cpu_percent}, Memory: {node_memory_percent}\n")

        csv_writer.writerow([cluster, node_name, node_cpu_usage, node_cpu_percent, node_memory_usage, node_memory_percent])
