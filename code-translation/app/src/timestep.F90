! timestep.F90 -- explicit stability limit of the diffusion terms, scaled by cfl.
real(kind=8) function stable_dt(cfg, dx, dy)
   use kinds, only: rk
   use config, only: config_t
   implicit none
   type(config_t), intent(in) :: cfg
   real(rk), intent(in) :: dx, dy

   stable_dt = cfg%cfl*min(dx, dy)**2/(4.0_rk*max(cfg%du, cfg%dv))
end function stable_dt
