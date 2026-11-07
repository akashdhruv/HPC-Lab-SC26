! output.F90 -- one diag line: step, time, masses, extrema, location of max v, coverage.
module output
   use kinds, only: rk
   use stats, only: stats_t
   implicit none
contains
   subroutine write_diag(step, time, s)
      integer, intent(in) :: step
      real(rk), intent(in) :: time
      type(stats_t), intent(in) :: s
      write (*, '(A,I7,5ES24.15E3,2I5,F10.6)') "diag", step, time, s%mass_u, s%mass_v, &
         s%max_v, s%min_u, s%imax, s%jmax, s%frac
   end subroutine write_diag
end module output
