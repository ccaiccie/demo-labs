# Comparable Path 2: Google Cloud IAP (Google Identity + IAM/CEL + Browser & gcloud Tunnel)

resource "google_compute_network" "iap_vpc" {
  count                   = var.enable_gcp ? 1 : 0
  name                    = "mc-iap-lab-vpc"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "iap_subnet" {
  count         = var.enable_gcp ? 1 : 0
  name          = "mc-iap-lab-subnet"
  ip_cidr_range = "10.30.0.0/24"
  region        = var.gcp_region
  network       = google_compute_network.iap_vpc[0].id
}

resource "google_compute_firewall" "iap_tcp" {
  count     = var.enable_gcp ? 1 : 0
  name      = "mc-iap-allow-tcp-from-iap"
  network   = google_compute_network.iap_vpc[0].name
  direction = "INGRESS"

  allow {
    protocol = "tcp"
    ports    = ["22", "3389"]
  }

  source_ranges = ["35.235.240.0/20"]
  target_tags   = ["mc-iap-vm"]
}

resource "google_compute_instance" "private_vm" {
  count        = var.enable_gcp ? 1 : 0
  name         = "mc-iap-private-vm"
  machine_type = "e2-micro"
  zone         = var.gcp_zone
  tags         = ["mc-iap-vm"]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.iap_subnet[0].id
    # No access_config -> no public IP
  }

  metadata = {
    enable-oslogin = "TRUE"
  }
}

resource "google_iap_tunnel_instance_iam_member" "tunnel_ssh" {
  count    = var.enable_gcp ? 1 : 0
  project  = var.gcp_project_id
  zone     = var.gcp_zone
  instance = google_compute_instance.private_vm[0].name
  role     = "roles/iap.tunnelResourceAccessor"
  member   = var.gcp_user_member

  condition {
    title      = "ssh-port-22-only"
    expression = "destination.port == 22"
  }
}
