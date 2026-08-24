################################################################################
# IAM role assumed by the External Secrets Operator controller
#
# The chain is:
#   pod (SA external-secrets/external-secrets)
#     -> Pod Identity agent injects credentials
#     -> STS AssumeRole against this role
#     -> role's inline policy allows reading one Secrets Manager prefix
################################################################################

data "aws_iam_policy_document" "eso_trust" {
  statement {
    effect = "Allow"

    # sts:TagSession is REQUIRED. Pod Identity attaches session tags
    # (cluster name, namespace, service account). Omitting this action
    # produces AccessDenied even when everything else is correct.
    actions = ["sts:AssumeRole", "sts:TagSession"]

    principals {
      type        = "Service"
      identifiers = ["pods.eks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "eso" {
  name               = "${local.name}-eso"
  description        = "Read-only access to demo secrets for External Secrets Operator"
  assume_role_policy = data.aws_iam_policy_document.eso_trust.json
}

data "aws_iam_policy_document" "eso_read" {
  statement {
    effect = "Allow"

    actions = [
      "secretsmanager:GetSecretValue",
      "secretsmanager:DescribeSecret",
    ]

    # The trailing wildcard is required: Secrets Manager appends a random
    # 6-character suffix to every secret ARN.
    #
    # Note this is scoped to ONE secret, not "*". If the ESO pod is ever
    # compromised, the blast radius is a single credential.
    resources = ["${aws_secretsmanager_secret.db.arn}*"]
  }
}

resource "aws_iam_role_policy" "eso" {
  name   = "read-demo-secrets"
  role   = aws_iam_role.eso.id
  policy = data.aws_iam_policy_document.eso_read.json
}

################################################################################
# Pod Identity association: maps a Kubernetes service account to the IAM role
#
# This is the single point where the AWS and Kubernetes worlds meet.
# The namespace and service account do not need to exist yet.
################################################################################

resource "aws_eks_pod_identity_association" "eso" {
  cluster_name    = module.eks.cluster_name
  namespace       = "external-secrets"
  service_account = "external-secrets"
  role_arn        = aws_iam_role.eso.arn
}
