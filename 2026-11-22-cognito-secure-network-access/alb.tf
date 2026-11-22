# -----------------------------------------------------------------------------
# Application Load Balancer with HTTPS `authenticate-cognito` Listener Action
# -----------------------------------------------------------------------------
# Key networking facts:
#   - `authenticate-cognito` is supported ONLY on HTTPS listeners.
#   - ALB communicates with Cognito's token and user-info endpoints over IPv4.
#   - If `var.alb_internal = true`, the ALB sits in private subnets and relies
#     on the NAT Gateway in network.tf to reach Cognito's public IPv4 endpoints.
#   - After authentication, ALB sets an encrypted session cookie and injects
#     X-AMZN-OIDC-ACCESSTOKEN, X-AMZN-OIDC-IDENTITY, and X-AMZN-OIDC-DATA
#     headers on requests forwarded to backend targets.
# -----------------------------------------------------------------------------

resource "aws_lb" "app" {
  name                       = "${var.project_name}-alb"
  internal                   = var.alb_internal
  load_balancer_type         = "application"
  security_groups            = [aws_security_group.alb.id]
  subnets                    = var.alb_internal ? aws_subnet.private[*].id : aws_subnet.public[*].id
  drop_invalid_header_fields = true

  tags = {
    Name = "${var.project_name}-alb"
  }
}

resource "aws_lb_target_group" "app" {
  name        = "${var.project_name}-tg"
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"

  health_check {
    path                = "/health"
    protocol            = "HTTP"
    matcher             = "200"
    healthy_threshold   = 2
    unhealthy_threshold = 2
  }
}

# HTTP (port 80) redirects unconditionally to HTTPS (port 443)
resource "aws_lb_listener" "http_redirect" {
  load_balancer_arn = aws_lb.app.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

# HTTPS (port 443) enforces Cognito sign-in before returning a response
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.app.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.acm_certificate_arn

  default_action {
    type  = "authenticate-cognito"
    order = 1

    authenticate_cognito {
      user_pool_arn              = aws_cognito_user_pool.public_edge.arn
      user_pool_client_id        = aws_cognito_user_pool_client.alb.id
      user_pool_domain           = aws_cognito_user_pool_domain.public_edge.domain
      scope                      = "openid email profile"
      on_unauthenticated_request = "authenticate"
      session_cookie_name        = "AWSELBAuthSessionCookie"
      session_timeout            = 3600
    }
  }

  # Fixed response allows immediate verification without launching EC2 targets;
  # see aws_lb_listener_rule.app_forward below for forwarding to backend targets.
  default_action {
    type  = "fixed-response"
    order = 2

    fixed_response {
      content_type = "text/plain"
      message_body = "Authenticated at the ALB via Amazon Cognito."
      status_code  = "200"
    }
  }
}

# Example rule showing authenticate-cognito chained into a backend target group
resource "aws_lb_listener_rule" "app_forward" {
  listener_arn = aws_lb_listener.https.arn
  priority     = 100

  condition {
    path_pattern {
      values = ["/app/*"]
    }
  }

  action {
    type  = "authenticate-cognito"
    order = 1

    authenticate_cognito {
      user_pool_arn              = aws_cognito_user_pool.public_edge.arn
      user_pool_client_id        = aws_cognito_user_pool_client.alb.id
      user_pool_domain           = aws_cognito_user_pool_domain.public_edge.domain
      scope                      = "openid email profile"
      on_unauthenticated_request = "authenticate"
    }
  }

  action {
    type             = "forward"
    order            = 2
    target_group_arn = aws_lb_target_group.app.arn
  }
}
