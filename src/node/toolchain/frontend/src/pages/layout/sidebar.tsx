/*
Copyright 2021 Toolchain Labs, Inc. All rights reserved.
Licensed under the Apache License, Version 2.0 (see LICENSE).
*/

import React, { useState } from 'react';
import { useTheme } from '@mui/material/styles';
import { useNavigate, useParams } from 'react-router-dom';
import Drawer from '@mui/material/Drawer';
import Divider from '@mui/material/Divider';
import IconButton from '@mui/material/IconButton';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import Menu from '@mui/icons-material/Menu';
import Grid from '@mui/material/Grid';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ButtonBase from '@mui/material/ButtonBase';
import Typography from '@mui/material/Typography';
import Chip from '@mui/material/Chip';
import VpnKeyIcon from '@mui/icons-material/VpnKey';
import FlagIcon from '@mui/icons-material/Flag';
import useMediaQuery from '@mui/material/useMediaQuery';
import Box from '@mui/material/Box';
import { styled } from '@mui/material/styles';

import OrganizationIcon from 'components/icons/organization-icon';
import QueryNames from 'common/enums/QueryNames';
import { useQueryGet } from 'utils/hooks/query';
import backends from 'utils/backend-paths';
import { ApiListResponse } from 'common/interfaces/api';
import { OrgRepoList, OrgList } from 'common/interfaces/orgs-repo';
import UserAvatar from 'components/users/user-avatar';
import { useUserContext } from 'store/user-store';
import ImpersionationBanner from 'components/impersonation-banner/impersonation-banner';
import AppInitData from 'common/interfaces/appInitData';
import paths from 'utils/paths';
import generateUrl from 'utils/url';
import { getHost } from 'utils/init-data';
import withExternalLink from 'utils/hoc/with-external-link/with-external-link';

type ReposByOrg = {
  [key: string]: {
    repos: OrgRepoList[];
    name: string;
    logoUrl: string;
  };
};
type OrgSectionProps = {
  orgSlug: string;
  logoUrl: string;
  orgName: string;
  repos: any[];
};
type SidebarProps = {
  toggleSidebar: () => void;
  supportLink?: string;
  reposByOrg: ReposByOrg;
  isImpersonating: boolean;
};
type StyledDrawerProps = {
  isClosed: boolean;
  isImpersonating: boolean;
};

const StyledDrawer = styled(Drawer, {
  shouldForwardProp: prop => !(['isClosed', 'isImpersonating'] as PropertyKey[]).includes(prop),
})<StyledDrawerProps>(({ theme, isClosed, isImpersonating }) => {
  const styles = isClosed
    ? {
        zIndex: '1301 !important' as unknown as 1301,
        width: '80px',
        [theme.breakpoints.down('md')]: {
          width: '100%',
          height: 56,
        },
      }
    : {
        zIndex: '1302 !important' as unknown as 1302,
        width: '360px',
        [theme.breakpoints.down('md')]: {
          width: '100%',
        },
      };
  const impersonationStyles = isImpersonating ? { height: 'calc(100% - 40px)', marginTop: theme.spacing(5) } : {};
  const padding = isClosed ? theme.spacing(1) : `0 ${theme.spacing(2)}`;
  return {
    flexShrink: 0,
    ...styles,
    [`& .MuiPaper-root`]: {
      ...impersonationStyles,
      ...styles,
      padding: padding,
      border: 0,
      backgroundColor: '#1C2B39',
      color: theme.palette.common.white,
      overflow: 'hidden',
    },
  };
});

const StyledCloseDrawerButton = styled(IconButton)(({ theme }) => ({
  position: 'absolute',
  top: theme.spacing(1),
  right: theme.spacing(3),
  zIndex: 10,
}));

const StyledOrganizationIconButton = styled(IconButton)(() => ({
  padding: 0,
}));

const StyledNoReposText = styled(Typography)(({ theme }) => ({
  color: theme.palette.grey[600],
}));

const StyledDivider = styled(Divider)(() => ({
  backgroundColor: 'rgba(0, 169, 183, 0.08)',
}));

const StyledActiveRepoDivider = styled(Divider)(({ theme }) => ({
  width: theme.spacing(0.5),
  height: theme.spacing(4),
  backgroundColor: theme.palette.primary.light,
  borderRadius: '2px',
}));

const StyledDividerProfile = styled(Divider)(({ theme }) => ({
  backgroundColor: 'rgba(0, 115, 124, 1)',
  position: 'relative',
  left: `-${theme.spacing(2)}`,
  width: 'calc(100% + 32px)',
}));

const StyledListItemButton = styled(ListItemButton)(({ theme }) => ({
  padding: `${theme.spacing(1)} ${theme.spacing(1)} ${theme.spacing(1)} ${theme.spacing(5)}`,
  [`&.Mui-selected`]: {
    background: 'rgba(255, 255, 255, 0.05)',
    color: theme.palette.primary.light,
    borderRadius: theme.spacing(1),
    [`&:hover`]: {
      background: 'rgba(255, 255, 255, 0.05)',
    },
  },
}));

const StyledCurrentChip = styled(Chip)(({ theme }) => ({
  backgroundColor: theme.palette.primary.light,
  color: theme.palette.common.white,
}));

const StyledMenuIconButton = styled(IconButton)(({ theme }) => ({
  marginTop: theme.spacing(1),
  [theme.breakpoints.down('md')]: {
    margin: 0,
  },
}));

const StyledUserContainer = styled(Grid)(({ theme }) => ({
  position: 'fixed',
  bottom: 0,
  marginBottom: 16,
  backgroundColor: '#1C2B39',
  width: 'calc(360px - 32px)',
  paddingTop: 16,
  [theme.breakpoints.down('md')]: {
    width: 'calc(100% - 32px)',
  },
}));

const StyledMenuButton = styled(IconButton)(() => ({
  borderRadius: 0,
  width: 'calc(360px - 32px)',
  padding: 0,
}));

const StyledIconLightFlag = styled(FlagIcon)(({ theme }) => ({
  color: theme.palette.primary.light,
}));

const StyledIconLightKey = StyledIconLightFlag.withComponent(VpnKeyIcon);

const StyledAvatarIconButton = styled(IconButton)(({ theme }) => ({
  width: '100%',
  textAlign: 'left',
  borderRadius: theme.spacing(1),
  backgroundColor: 'rgba(0, 169, 183, 0.08)',
  padding: 0,
}));

const StyledOrgList = styled(List)(() => ({
  height: '82vh',
  overflow: 'auto',
  [`&::-webkit-scrollbar`]: {
    opacity: 0,
  },
}));

const StyledSidebarShadeWrapper = styled(Grid)(({ theme }) => ({
  pointerEvents: 'none',
  zIndex: 200,
  position: 'absolute',
  left: 0,
  bottom: 201,
  width: 360,
  [theme.breakpoints.down('md')]: {
    width: '100%',
  },
}));

const StyledSidebarShade = styled(Box)(() => ({
  height: 64,
  width: '100%',
  background: 'linear-gradient(180deg, rgba(28, 43, 57, 0) 0%, #1C2B39 100%)',
}));

const ClosedSidebar = ({ toggleSidebar, reposByOrg, isImpersonating }: SidebarProps) => {
  const { orgSlug } = useParams();
  const { user } = useUserContext();
  const showOrganizationIcon = !!reposByOrg[orgSlug];

  const theme = useTheme();
  const matchesMobile = useMediaQuery(theme.breakpoints.down('md'));
  const gridDirection = matchesMobile ? 'row' : 'column';
  const drawerAnchor = matchesMobile ? 'top' : 'left';
  const avatarSize = matchesMobile ? 'extraSmall' : 'small';

  const menuIcon = showOrganizationIcon ? (
    <Grid container spacing={2} alignItems="center">
      <Grid item>
        <StyledOrganizationIconButton onClick={toggleSidebar} size="large">
          <OrganizationIcon url={reposByOrg[orgSlug].logoUrl} slug={orgSlug} size={avatarSize} />
        </StyledOrganizationIconButton>
      </Grid>
      <Grid item sx={{ display: { md: 'none', xs: 'block' } }}>
        <Typography variant="h3">{reposByOrg[orgSlug].name}</Typography>
      </Grid>
    </Grid>
  ) : (
    <StyledMenuIconButton aria-label="open menu" onClick={() => toggleSidebar()} size="large">
      <Menu color="primary" />
    </StyledMenuIconButton>
  );

  return (
    <StyledDrawer
      variant="permanent"
      anchor={drawerAnchor}
      isClosed={true}
      isImpersonating={isImpersonating}
      onClick={e => {
        e.stopPropagation();
      }}
    >
      <Grid
        container
        direction={gridDirection}
        justifyContent="space-between"
        alignItems="center"
        wrap="nowrap"
        height="100%"
      >
        <Grid item sm="auto">
          {menuIcon}
        </Grid>
        <Grid item sm="auto">
          <IconButton onClick={toggleSidebar} size="large" sx={{ p: 0 }}>
            <UserAvatar url={user?.avatar_url} size={avatarSize} userFullName={user?.full_name || user?.username} />
          </IconButton>
        </Grid>
      </Grid>
    </StyledDrawer>
  );
};

const OpenedSidebar = ({
  toggleSidebar,
  reposByOrg,
  supportLink,
}: Pick<SidebarProps, 'reposByOrg' | 'toggleSidebar' | 'supportLink'>) => {
  const { user } = useUserContext();
  const navigate = useNavigate();
  const { orgSlug: currentOrg, repoSlug: currentRepo } = useParams();

  const signOut = (e: React.SyntheticEvent) => {
    e.preventDefault();
    window.location.assign(generateUrl(backends.users_ui.LOGOUT, getHost()));
  };
  const goToTokens = (e: React.SyntheticEvent) => {
    e.preventDefault();
    navigate('/tokens/');
    toggleSidebar();
  };
  const goToProfile = (e: React.SyntheticEvent) => {
    e.preventDefault();
    navigate('/profile/');
    toggleSidebar();
  };

  const GoToSupportLink = withExternalLink(
    () => (
      <StyledMenuButton size="large">
        <Grid container direction="row" spacing={1} alignItems="center">
          <Grid item>
            <StyledIconLightFlag />
          </Grid>
          <Grid item>
            <Typography variant="body1" color="white">
              Report issues
            </Typography>
          </Grid>
        </Grid>
      </StyledMenuButton>
    ),
    supportLink,
    null
  );

  const OrgSection = ({ orgSlug, orgName, logoUrl, repos }: OrgSectionProps) => {
    const repoListItems = repos.map(repo => {
      const isActiveRepo = orgSlug === currentOrg && repo.slug === currentRepo;
      const handleRepoLink = () => {
        navigate({ pathname: paths.builds(orgSlug, repo.slug), search: '?user=me' });
        toggleSidebar();
      };

      return (
        <StyledListItemButton onClick={handleRepoLink} key={repo.slug} selected={isActiveRepo}>
          <Grid container alignItems="center" justifyContent="space-between">
            <Grid item>
              <Typography variant="subtitle1">{repo.name}</Typography>
            </Grid>
            {isActiveRepo && <StyledActiveRepoDivider />}
          </Grid>
        </StyledListItemButton>
      );
    });

    const handleOrgLink = () => {
      navigate(paths.organization(orgSlug));
      toggleSidebar();
    };

    const noRepos = repoListItems.length === 0;
    const isCurrentOrg = currentOrg === orgSlug;

    const extraInfo = isCurrentOrg ? (
      <StyledCurrentChip size="small" label="current" />
    ) : (
      (noRepos && <StyledNoReposText variant="body2">No repo in this organization</StyledNoReposText>) || null
    );

    return (
      <>
        <ListItem disableGutters>
          <Grid container wrap="nowrap" alignItems="center" spacing={2}>
            <Grid item>
              <OrganizationIcon slug={orgSlug} url={logoUrl} size="small" />
            </Grid>
            <Grid item>
              <Grid container>
                <Grid item xs={12}>
                  <ButtonBase onClick={handleOrgLink}>
                    <Typography variant="h3" align="left">
                      {orgName}
                    </Typography>
                  </ButtonBase>
                </Grid>
                <Grid item xs={12}>
                  {extraInfo}
                </Grid>
              </Grid>
            </Grid>
          </Grid>
        </ListItem>
        <List>
          <Grid container spacing={3}>
            <Grid item xs={12}>
              {repoListItems}
            </Grid>
            <Grid item xs={12}>
              <StyledDivider />
            </Grid>
          </Grid>
        </List>
      </>
    );
  };

  const RepoList = () => (
    <StyledOrgList>
      {Object.entries(reposByOrg).map(([key, value]) => {
        const orgSlug = key;
        const { name: orgName, logoUrl, repos } = value;
        return <OrgSection orgSlug={orgSlug} key={orgSlug} logoUrl={logoUrl} orgName={orgName} repos={repos} />;
      })}
    </StyledOrgList>
  );

  return (
    <Grid container direction="row" justifyContent="space-between" height="100%" alignItems="flex-start">
      <Grid container item direction="column" justifyContent="flex-start" xs={12}>
        <Grid item container direction="column" alignItems="flex-end" position="absolute">
          <Grid item>
            <StyledCloseDrawerButton aria-label="Close drawer" onClick={() => toggleSidebar()} size="large">
              <ChevronLeftIcon color="primary" fontSize="medium" />
            </StyledCloseDrawerButton>
          </Grid>
        </Grid>
        <Grid item>
          <RepoList />
        </Grid>
      </Grid>
      <StyledSidebarShadeWrapper item>
        <StyledSidebarShade />
        <StyledDividerProfile />
      </StyledSidebarShadeWrapper>
      {user && (
        <StyledUserContainer item xs={12}>
          <Grid container>
            <Grid item xs={12}>
              <Grid container direction="column" spacing={2}>
                <Grid item xs={12}>
                  <StyledAvatarIconButton onClick={goToProfile} size="large">
                    <Grid container alignItems="center" wrap="nowrap" spacing={2}>
                      <Grid item>
                        <UserAvatar
                          url={user?.avatar_url}
                          size="small"
                          userFullName={user?.full_name || user?.username}
                        />
                      </Grid>
                      <Grid item>
                        <Grid container>
                          <Grid item xs={12}>
                            <Typography variant="caption" color="white">
                              @{user.username}
                            </Typography>
                          </Grid>
                          <Grid item xs={12}>
                            <Typography variant="h3" color="white">
                              {user.full_name}
                            </Typography>
                          </Grid>
                        </Grid>
                      </Grid>
                    </Grid>
                  </StyledAvatarIconButton>
                </Grid>
                <Grid item xs={12}>
                  <Grid container alignItems="center">
                    <Grid item xs={12}>
                      <StyledMenuButton onClick={goToTokens} size="large">
                        <Grid container direction="row" spacing={1} alignItems="center">
                          <Grid item>
                            <StyledIconLightKey />
                          </Grid>
                          <Grid item>
                            <Typography variant="body1" color="white">
                              Pants client tokens
                            </Typography>
                          </Grid>
                        </Grid>
                      </StyledMenuButton>
                    </Grid>
                    <Grid item xs={1}>
                      <GoToSupportLink />
                    </Grid>
                    <Grid item xs={12}>
                      <IconButton onClick={signOut} sx={{ p: 0 }} size="large">
                        <Typography variant="body1" color="error">
                          Sign out
                        </Typography>
                      </IconButton>
                    </Grid>
                  </Grid>
                </Grid>
              </Grid>
            </Grid>
          </Grid>
        </StyledUserContainer>
      )}
    </Grid>
  );
};

const Sidebar = () => {
  const [{ data: orgData }] = useQueryGet<ApiListResponse<OrgList>>(
    [QueryNames.ORGS],
    backends.users_api.LIST_ORGANIZATIONS,
    null,
    { refetchOnMount: false }
  );
  const [{ data: orgsReposData }] = useQueryGet<OrgRepoList[]>(
    [QueryNames.ALL_USER_REPOS],
    backends.users_api.LIST_ALL_REPOS,
    null,
    { enabled: !!orgData, refetchOnMount: false }
  );

  const [drawerOpen, setDrawerOpen] = useState(false);

  const reposByOrg: ReposByOrg = {};
  if (orgsReposData && orgData?.results) {
    const orgs = orgData.results;

    orgs.forEach(org => {
      reposByOrg[org.slug] = { name: org.name, logoUrl: org.logo_url, repos: [] };
    });

    orgsReposData.forEach(repo => {
      if (repo.customer_slug in reposByOrg) {
        reposByOrg[repo.customer_slug].repos.push(repo);
      }
    });
  }

  const appInitDataElement: HTMLElement | null = document.getElementById('app_init_data');
  const appInitDataElementInner: string = appInitDataElement?.innerText;
  const appInitData: AppInitData = appInitDataElementInner && JSON.parse(atob(appInitDataElementInner?.trim()));
  const isImpersonating = appInitData && !!appInitData.impersonation;
  const supportLink = appInitData && appInitData.support_link;

  return (
    <>
      {isImpersonating && <ImpersionationBanner impersonationData={appInitData.impersonation} />}
      <StyledDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        isClosed={false}
        isImpersonating={isImpersonating}
        onClick={e => e.stopPropagation()}
      >
        <OpenedSidebar reposByOrg={reposByOrg} toggleSidebar={() => setDrawerOpen(false)} supportLink={supportLink} />
      </StyledDrawer>
      <ClosedSidebar
        reposByOrg={reposByOrg}
        toggleSidebar={() => setDrawerOpen(true)}
        isImpersonating={isImpersonating}
      />
    </>
  );
};

export default Sidebar;
