! reaction.F90 -- Gray-Scott reaction terms, elemental so they apply to whole arrays.
module reaction
   use kinds, only: rk
   implicit none
contains
   elemental real(rk) function react_u(u, v, feed)
      real(rk), intent(in) :: u, v, feed
      react_u = -u*v*v+feed*(1.0_rk-u)
   end function react_u

   elemental real(rk) function react_v(u, v, feed, kill)
      real(rk), intent(in) :: u, v, feed, kill
      react_v = u*v*v-(feed+kill)*v
   end function react_v
end module reaction
