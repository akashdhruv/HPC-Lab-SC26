! stats.F90 -- diagnostics of the fields: masses, extrema, location of max v, coverage.
module stats
   use kinds, only: rk
   implicit none

   type :: stats_t
      real(rk) :: mass_u, mass_v, max_v, min_u, frac
      integer :: imax, jmax
   end type stats_t

contains

   subroutine compute_stats(s, u, v, nx, ny, dx, dy)
      type(stats_t), intent(out) :: s
      integer, intent(in) :: nx, ny
      real(rk), intent(in) :: u(0:nx+1, 0:ny+1), v(0:nx+1, 0:ny+1), dx, dy
      integer :: loc(2)

      s%mass_u = sum(u(1:nx, 1:ny))*dx*dy
      s%mass_v = sum(v(1:nx, 1:ny))*dx*dy
      s%max_v = maxval(v(1:nx, 1:ny))
      s%min_u = minval(u(1:nx, 1:ny))
      loc = maxloc(v(1:nx, 1:ny))
      s%imax = loc(1)
      s%jmax = loc(2)
      s%frac = real(count(v(1:nx, 1:ny) > 0.25_rk), rk)/real(nx*ny, rk)
   end subroutine compute_stats

end module stats
