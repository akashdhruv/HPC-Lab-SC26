! driver.F90 -- set up, time loop, diagnostics every interval steps.
subroutine run_simulation(cfg)
   use kinds, only: rk
   use config, only: config_t
   use grid, only: g, grid_init, grid_free
   use stats, only: stats_t, compute_stats
   use output, only: write_diag
   implicit none
   type(config_t), intent(in) :: cfg

   real(rk), external :: stable_dt
   type(stats_t) :: s
   real(rk) :: dt, time
   integer :: step

   call grid_init(cfg)
   call initial(cfg)
   dt = stable_dt(cfg, g%dx, g%dy)
   time = 0.0_rk
   print '(A,ES12.5)', " driver: dt = ", dt

   call compute_stats(s, g%u, g%v, g%nx, g%ny, g%dx, g%dy)
   call write_diag(0, time, s)
   do step = 1, cfg%nsteps
      call advance(cfg, dt)
      time = time+dt
      if (mod(step, cfg%interval) == 0) then
         call compute_stats(s, g%u, g%v, g%nx, g%ny, g%dx, g%dy)
         call write_diag(step, time, s)
      end if
   end do
   call grid_free()
end subroutine run_simulation
