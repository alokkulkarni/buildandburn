resource "aws_vpc" "main" {
  cidr_block           = var.cidr_block
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.env_id}-vpc"
    }
  )
}

# Fetch availability zones
data "aws_availability_zones" "available" {}

locals {
  az_count = min(length(data.aws_availability_zones.available.names), 3)
  azs      = slice(data.aws_availability_zones.available.names, 0, local.az_count)
}

# Public subnets
resource "aws_subnet" "public" {
  count                   = local.az_count
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.cidr_block, 8, count.index)
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = true

  tags = merge(
    var.tags,
    {
      Name                                                              = "${var.project_name}-${var.env_id}-public-${local.azs[count.index]}"
      "kubernetes.io/role/elb"                                          = "1"
      "kubernetes.io/cluster/${var.project_name}-${var.env_id}-cluster" = "shared"
    }
  )
}

# Private subnets
resource "aws_subnet" "private" {
  count                   = local.az_count
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.cidr_block, 8, count.index + local.az_count)
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = false

  tags = merge(
    var.tags,
    {
      Name                                                              = "${var.project_name}-${var.env_id}-private-${local.azs[count.index]}"
      "kubernetes.io/role/internal-elb"                                 = "1"
      "kubernetes.io/cluster/${var.project_name}-${var.env_id}-cluster" = "shared"
    }
  )
}

# Database subnets
resource "aws_subnet" "database" {
  count                   = local.az_count
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.cidr_block, 8, count.index + 2 * local.az_count)
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = false

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.env_id}-database-${local.azs[count.index]}"
    }
  )
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.env_id}-igw"
    }
  )
}

# Elastic IPs for NAT Gateways
resource "aws_eip" "nat" {
  count = 1 # Changed from local.az_count to 1
  # domain = "vpc"

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.env_id}-eip-nat"
    }
  )
}

# NAT Gateways - Only create one for all AZs
resource "aws_nat_gateway" "main" {
  count         = 1 # Changed from local.az_count to 1
  allocation_id = aws_eip.nat[0].id
  subnet_id     = aws_subnet.public[0].id # Using the first public subnet

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.env_id}-nat"
    }
  )

  depends_on = [aws_internet_gateway.main]
}

# Route table for public subnets
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.env_id}-public-rt"
    }
  )
}

# Route tables for private subnets
resource "aws_route_table" "private" {
  count  = local.az_count
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main[0].id # All private subnets use the same NAT gateway
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.env_id}-private-rt-${count.index}"
    }
  )
}

# Route table for database subnets
resource "aws_route_table" "database" {
  count  = local.az_count
  vpc_id = aws_vpc.main.id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main[0].id # All database subnets use the same NAT gateway
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.project_name}-${var.env_id}-database-rt-${count.index}"
    }
  )
}

# Route table associations for public subnets
resource "aws_route_table_association" "public" {
  count          = local.az_count
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

# Route table associations for private subnets
resource "aws_route_table_association" "private" {
  count          = local.az_count
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[count.index].id
}

# Route table associations for database subnets
resource "aws_route_table_association" "database" {
  count          = local.az_count
  subnet_id      = aws_subnet.database[count.index].id
  route_table_id = aws_route_table.database[count.index].id
} 