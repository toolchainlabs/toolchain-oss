/*
Copyright 2022 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { useState } from 'react';
import Card from '@mui/material/Card';
import Grid from '@mui/material/Grid';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import Tooltip, { TooltipProps } from '@mui/material/Tooltip';
import Snackbar from '@mui/material/Snackbar';
import MuiAlert from '@mui/material/Alert';
import IconButton from '@mui/material/IconButton';
import OpenInNew from '@mui/icons-material/OpenInNew';
import Close from '@mui/icons-material/Close';
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline';

import { OrganizationPlanAndUsage } from 'common/interfaces/orgs-repo';
import QueryNames from 'common/enums/QueryNames';
import { useMutationPost, useQueryGet } from 'utils/hooks/query';
import backends from 'utils/backend-paths';
import { daysLeftUntillDate } from 'utils/datetime-formats';
import withLoadingAndError from 'utils/hoc/with-loading-and-error/with-loading-and-error';
import { styled } from '@mui/material/styles';

type CardProps = { billingUrl: string; orgSlug: string };
type PlanCardProps = Pick<CardProps, 'billingUrl'> & { data?: OrganizationPlanAndUsage };

const StyledCard = styled(Card)(({ theme }) => ({
  background: theme.palette.common.white,
  borderRadius: theme.spacing(1),
  padding: theme.spacing(5),
  boxShadow: 'unset',
  position: 'relative',
}));

const NoPlanCard = styled(Card)(({ theme }) => ({
  background: theme.palette.grey[200],
  borderRadius: theme.spacing(1),
  padding: theme.spacing(5),
  boxShadow: 'unset',
  border: `1px dashed ${theme.palette.text.disabled}`,
  color: theme.palette.text.secondary,
}));

const Triangle = styled('div')(({ theme }) => ({
  zIndex: 1,
  position: 'absolute',
  left: 0,
  top: 0,
  borderTop: `28px solid ${theme.palette.primary.dark}`,
  borderRight: `46px solid transparent`,
  borderBottom: `28px solid transparent`,
  borderLeft: `46px solid ${theme.palette.primary.dark}`,
}));

const Gradient = styled('div')(() => ({
  zIndex: 1,
  height: '35vh',
  position: 'absolute',
  top: 0,
  left: 0,
  right: 0,
  backgroundImage: `linear-gradient(108.43deg, rgba(0, 169, 183, 0.08) 0%, rgba(0, 169, 183, 0) 99.99%)`,
  backgroundAttachment: 'fixed',
  backgroundPosition: 'center',
  clipPath: `polygon(100% 100%, 0 0, 100vw 0)`,
}));

const ManagePlanButton = styled(Button)(() => ({
  zIndex: 5,
  position: 'absolute',
  top: 40,
  right: 40,
}));

const ManagePlanDiv = styled('div')(() => ({
  zIndex: 5,
  position: 'absolute',
  top: 40,
  right: 40,
}));

const WordBreak = styled(Typography)(() => ({
  wordWrap: 'break-word',
}));

const TrialText = styled(Typography)(({ theme }) => ({
  borderRadius: theme.spacing(2),
  border: `1px solid ${theme.palette.primary.main}`,
  padding: `3px ${theme.spacing(1)}`,
}));

const InfoIcon = styled(ErrorOutlineIcon)(() => ({
  cursor: 'pointer',
  zIndex: 3,
}));

const BulletList = styled('ul')(({ theme }) => ({
  padding: `0px ${theme.spacing(2)}`,
  margin: 0,
}));

const ToBeStyledTooltip = ({ className, children, title, ...props }: TooltipProps) => {
  return <Tooltip {...props} classes={{ tooltip: className }} children={children} title={title} />;
};
const StyledTooltip = styled(ToBeStyledTooltip)(({ theme }) => ({
  padding: `${theme.spacing(2)} ${theme.spacing(3)}`,
  backgroundColor: 'rgba(28, 43, 57, 1)',
  width: 400,
}));

const PlanCard = ({ billingUrl, data }: PlanCardProps) => {
  const [billingError, setBillingError] = useState(null);

  const [{ isLoading: isLoadingPost, mutate: mutatePost }] = useMutationPost(
    [`${QueryNames.BILLING}/${billingUrl}`],
    billingUrl,
    null,
    {
      onError: (error: any) => {
        if (error.error?.detail) {
          setBillingError(error.error.detail);
        } else {
          setBillingError('Something wrong happened, please try again');
        }
      },
      onSuccess: ({ session_url }: { session_url: string }) => window.location.assign(session_url),
    },
    true
  );

  if (!data?.plan) {
    return (
      <Grid item xs={12}>
        <NoPlanCard>
          <Typography variant="h3" align="center">
            Plan information not available at the moment
          </Typography>
        </NoPlanCard>
      </Grid>
    );
  }

  const { name, price, trial_end: trialEnd, resources } = data?.plan || {};
  const { inbound, outbound } = data?.usage?.bandwidth || {};
  const isEnterprise = name === 'Enterprise';

  const getStripeUrl = () => mutatePost({});
  const trialDaysLeft = trialEnd && daysLeftUntillDate(trialEnd) + 1;
  const hasTrialEnded = trialDaysLeft <= 0;
  const hasMoreThanOneDayLeft = trialDaysLeft > 1;

  const LabelValue = ({ label, value }: { label: string; value: string }) => (
    <Grid container spacing={1}>
      <Grid item xs={12}>
        <Typography variant="overline" color="text.disabled">
          {label}
        </Typography>
      </Grid>
      <Grid item xs={12}>
        <WordBreak variant="body1">{value}</WordBreak>
      </Grid>
    </Grid>
  );

  const planTooltip = (
    <Grid container spacing={2}>
      <Grid item xs={12}>
        <Grid container spacing={1}>
          <Grid item xs={12}>
            <Typography color="primary.light" variant="subtitle2">
              Data usage
            </Typography>
          </Grid>
          <Grid item xs={12}>
            <Typography variant="caption">All usage data are for the current month to date.</Typography>
          </Grid>
        </Grid>
      </Grid>
      <Grid item xs={12}>
        <Grid container spacing={1}>
          <Grid item xs={12}>
            <Typography color="primary.light" variant="subtitle2">
              About this plan
            </Typography>
          </Grid>
          <Grid item xs={12}>
            <BulletList>
              {resources?.map(resource => (
                <li key={resource}>
                  <Typography variant="caption">{resource}</Typography>
                </li>
              ))}
            </BulletList>
          </Grid>
        </Grid>
      </Grid>
    </Grid>
  );

  return !!data ? (
    <>
      <StyledCard>
        {isEnterprise && (
          <>
            <Triangle />
            <Gradient />
          </>
        )}
        <Grid container spacing={3} justifyContent="space-between">
          <Grid item xs={12} zIndex={3}>
            <Grid container spacing={3}>
              <Grid item xs={12}>
                <Grid container spacing={2} alignItems="center">
                  <Grid item>
                    <Typography variant="h3">{name}</Typography>
                  </Grid>
                  {trialDaysLeft ? (
                    <Grid item>
                      <TrialText variant="caption">
                        {hasTrialEnded
                          ? 'Trial has ended'
                          : `Trial ends in ${trialDaysLeft} day${hasMoreThanOneDayLeft ? 's' : ''}`}
                      </TrialText>
                    </Grid>
                  ) : null}
                  <Grid item display="flex">
                    <Tooltip title={planTooltip} arrow placement="right-start">
                      <InfoIcon color="primary" />
                    </Tooltip>
                  </Grid>
                </Grid>
              </Grid>
              <Grid item xs={12}>
                <Grid container spacing={5}>
                  <Grid item>
                    <LabelValue label="PRICE" value={price} />
                  </Grid>
                  <Grid item>
                    <LabelValue label="INBOUND TRANSFER USAGE" value={inbound ? `${inbound} used` : 'Not available'} />
                  </Grid>
                  <Grid item>
                    <LabelValue
                      label="OUTBOUND TRANSFER USAGE"
                      value={outbound ? `${outbound} used` : 'Not available'}
                    />
                  </Grid>
                </Grid>
              </Grid>
            </Grid>
          </Grid>
        </Grid>
        {billingUrl ? (
          <ManagePlanButton
            variant="outlined"
            disabled={isLoadingPost}
            startIcon={<OpenInNew />}
            onClick={getStripeUrl}
          >
            <Typography variant="button1"> MANAGE PLAN</Typography>
          </ManagePlanButton>
        ) : (
          <StyledTooltip
            title={
              <Grid container spacing={2} sx={{ maxWidth: 192 }}>
                <Grid item xs={12}>
                  <Typography variant="subtitle2" color="primary">
                    Admin access
                  </Typography>
                </Grid>
                <Grid item xs={12}>
                  <Typography variant="caption">Only admin users can manage the subscription plan.</Typography>
                </Grid>
              </Grid>
            }
            arrow
            placement="top-end"
          >
            <ManagePlanDiv>
              <Button variant="outlined" color="primary" startIcon={<OpenInNew />} disabled={true}>
                <Typography variant="button1"> MANAGE PLAN</Typography>
              </Button>
            </ManagePlanDiv>
          </StyledTooltip>
        )}
      </StyledCard>
      <Snackbar
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        autoHideDuration={5000}
        open={Boolean(billingError)}
        onClose={() => setBillingError(null)}
      >
        <MuiAlert
          icon={false}
          severity="error"
          variant="filled"
          onClose={() => setBillingError(null)}
          action={
            <IconButton size="small" aria-label="close" color="inherit" onClick={() => setBillingError(null)}>
              <Close />
            </IconButton>
          }
        >
          {billingError}
        </MuiAlert>
      </Snackbar>
    </>
  ) : null;
};

const OrganizationPlan = ({ billingUrl, orgSlug }: CardProps) => {
  const [{ data, isFetching, errorMessage }] = useQueryGet<OrganizationPlanAndUsage>(
    [`${orgSlug}/${QueryNames.ORG_PLAN}`],
    backends.users_api.ORGANIZATION_PLAN(orgSlug)
  );

  const WrappedComponent = withLoadingAndError(PlanCard, data, isFetching, errorMessage);

  return <WrappedComponent billingUrl={billingUrl} />;
};

export default OrganizationPlan;
